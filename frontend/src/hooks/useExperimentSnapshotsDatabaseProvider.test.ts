import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useExperimentSnapshotsDatabaseProvider } from './useExperimentSnapshotsDatabaseProvider'
import {
  READ_FAILED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  useEvalsStore,
  useTraceStore,
  type ExperimentSnapshotWorkerProxy,
} from '@luml/experiments'

const mocks = vi.hoisted(() => {
  const store = {
    experimentSnapshotProvider: null as unknown,
    releaseProvider: null as (() => void) | null,
    getDownloadUrl: vi.fn(),
    renewDownloadUrl: vi.fn(),
    downloadUrlSource: vi.fn(() => ({
      getLocation: store.getDownloadUrl,
      renewLocation: store.renewDownloadUrl,
    })),
    getFileFromBucket: vi.fn(),
    setExperimentSnapshotProvider: vi.fn((provider: unknown, onRelease?: () => void) => {
      const releasePrevious = store.releaseProvider
      store.experimentSnapshotProvider = provider
      store.releaseProvider = onRelease ?? null
      releasePrevious?.()
    }),
    resetExperimentSnapshotProvider: vi.fn(() => {
      const releasePrevious = store.releaseProvider
      store.experimentSnapshotProvider = null
      store.releaseProvider = null
      releasePrevious?.()
    }),
  }
  return store
})

const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: toastAdd }),
}))

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => mocks,
}))

vi.mock('@/lib/bucket-service', () => ({
  ModelDownloader: class {
    getFileFromBucket = mocks.getFileFromBucket
  },
}))

vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: {
    findExperimentSnapshotArchiveName: (fileIndex: Record<string, unknown>) =>
      Object.keys(fileIndex)[0] ?? 'exp.db.zip',
  },
}))

class MockWorker extends EventTarget {
  readonly terminate = vi.fn()
  readonly postMessage = vi.fn()
  readonly listeners = new Set<EventListenerOrEventListenerObject>()

  override addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.add(listener)
    super.addEventListener(type, listener)
  }

  override removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.delete(listener)
    super.removeEventListener(type, listener)
  }

  emit(data: unknown) {
    this.dispatchEvent(new MessageEvent('message', { data }))
  }
}

let init: ReturnType<typeof useExperimentSnapshotsDatabaseProvider>['init']
let workers: MockWorker[]
let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

const ZIP_MEMBER_SIZE = 1_000_000
const ZIP_TAIL_BYTES = 128 * 1024

/**
 * The last 128 KiB of a zip member of `ZIP_MEMBER_SIZE` bytes, ending in a directory whose only
 * entry, `exp.db`, claims `size` bytes.
 */
function zipDirectoryTail(size: number): Uint8Array {
  const name = new TextEncoder().encode('exp.db')
  const tail = new Uint8Array(ZIP_TAIL_BYTES)
  const view = new DataView(tail.buffer)
  const directorySize = 46 + name.length
  const directory = ZIP_TAIL_BYTES - directorySize - 22
  view.setUint32(directory, 0x02014b50, true)
  view.setUint32(directory + 20, size, true)
  view.setUint32(directory + 24, size, true)
  view.setUint16(directory + 28, name.length, true)
  tail.set(name, directory + 46)
  const end = directory + directorySize
  view.setUint32(end, 0x06054b50, true)
  view.setUint16(end + 8, 1, true)
  view.setUint16(end + 10, 1, true)
  view.setUint32(end + 12, directorySize, true)
  view.setUint32(end + 16, ZIP_MEMBER_SIZE - ZIP_TAIL_BYTES + directory, true)
  return tail
}

const Harness = defineComponent({
  setup() {
    init = useExperimentSnapshotsDatabaseProvider().init
    return () => h('div')
  },
})

describe('experiment snapshot worker lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.experimentSnapshotProvider = null
    mocks.releaseProvider = null
    workers = []
    fetchMock = vi.fn<typeof fetch>(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal(
      'Worker',
      class extends MockWorker {
        constructor() {
          super()
          workers.push(this)
        }
      },
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  async function initialize(worker: MockWorker, initialized: Promise<void>) {
    await Promise.resolve()
    const [message] = worker.postMessage.mock.calls[worker.postMessage.mock.calls.length - 1]
    expect(message.type).toBe('init')
    worker.emit({ type: 'result', requestId: message.requestId, data: true })
    await initialized
  }

  it('keeps the worker alive while its provider stays in the store after unmount', async () => {
    const wrapper = mount(Harness)
    await initialize(workers[0], init([]))
    const worker = workers[0]

    expect(mocks.setExperimentSnapshotProvider).toHaveBeenCalledOnce()
    wrapper.unmount()
    expect(worker.terminate).not.toHaveBeenCalled()

    mocks.resetExperimentSnapshotProvider()
    expect(worker.terminate).toHaveBeenCalledOnce()
  })

  it('terminates the worker of an unmounted view when another provider replaces it', async () => {
    const first = mount(Harness)
    await initialize(workers[0], init([]))
    first.unmount()

    const second = mount(Harness)
    await initialize(workers[1], init([]))

    expect(workers[0].terminate).toHaveBeenCalledOnce()
    expect(workers[1].terminate).not.toHaveBeenCalled()
    second.unmount()
  })

  it('rejects a pending init when the worker crashes', async () => {
    const wrapper = mount(Harness)
    const initialized = init([])
    const rejection = expect(initialized).rejects.toThrow('worker crashed')
    await Promise.resolve()

    const worker = workers[0]
    worker.dispatchEvent(new ErrorEvent('error', { message: 'worker crashed' }))

    await rejection
    expect(worker.listeners.size).toBe(0)
    expect(mocks.setExperimentSnapshotProvider).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('rejects calls left in flight when the worker is terminated', async () => {
    const wrapper = mount(Harness)
    const worker = workers[0]
    await initialize(worker, init([]))
    const provider = mocks.experimentSnapshotProvider as ExperimentSnapshotWorkerProxy
    wrapper.unmount()

    const inFlight = provider.resetTracesRequestParams()
    mocks.resetExperimentSnapshotProvider()

    await expect(inFlight).rejects.toThrow(/terminated/i)
    await expect(provider.resetEvalsDatasetsRequestParams()).rejects.toThrow(/terminated/i)
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(worker.listeners.size).toBe(0)
  })

  it('shows no toast for a viewer read cut off when the closed view terminates the worker', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(Harness)
    const worker = workers[0]
    await initialize(worker, init([]))
    useEvalsStore().setProvider(mocks.experimentSnapshotProvider as ExperimentSnapshotWorkerProxy)

    const refresh = useTraceStore().refresh()
    expect(worker.postMessage).toHaveBeenLastCalledWith(
      expect.objectContaining({ payload: expect.objectContaining({ method: 'getFreshTraces' }) }),
    )
    wrapper.unmount()
    mocks.resetExperimentSnapshotProvider()
    await refresh
    await flushPromises()

    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(toastAdd).not.toHaveBeenCalled()
  })

  it('reuses the worker when the provider is reset while the view is mounted', async () => {
    const wrapper = mount(Harness)
    const worker = workers[0]
    await initialize(worker, init([]))

    mocks.resetExperimentSnapshotProvider()
    await initialize(worker, init([]))

    expect(worker.terminate).not.toHaveBeenCalled()
    expect(mocks.experimentSnapshotProvider).not.toBeNull()
    wrapper.unmount()
  })

  it('aborts an in-flight worker init and removes its listeners on unmount', async () => {
    const wrapper = mount(Harness)
    const initialized = init([])
    const rejection = expect(initialized).rejects.toMatchObject({ name: 'AbortError' })
    await Promise.resolve()

    const worker = workers[0]
    const [message] = worker.postMessage.mock.calls[0]
    wrapper.unmount()

    await rejection
    expect(worker.postMessage).toHaveBeenLastCalledWith({
      type: 'cancel',
      requestId: message.requestId,
    })
    expect(worker.listeners.size).toBe(0)
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(mocks.setExperimentSnapshotProvider).not.toHaveBeenCalled()
  })

  it('does not start a download or post to the worker after unmount', async () => {
    let resolveUrl!: (url: string) => void
    mocks.getDownloadUrl.mockReturnValueOnce(
      new Promise<string>((resolve) => {
        resolveUrl = resolve
      }),
    )
    const wrapper = mount(Harness)
    const model = { id: 'model-1', name: 'model', file_index: [] } as unknown as ModelArtifact
    const initialized = init([model])
    const rejection = expect(initialized).rejects.toMatchObject({ name: 'AbortError' })
    await Promise.resolve()

    const worker = workers[0]
    wrapper.unmount()
    resolveUrl('https://example.com/snapshot')

    await rejection
    expect(mocks.getFileFromBucket).not.toHaveBeenCalled()
    expect(worker.postMessage).not.toHaveBeenCalled()
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(mocks.setExperimentSnapshotProvider).not.toHaveBeenCalled()
  })

  it('downloads a zipped snapshot whole and hands a raw snapshot to the worker as a range source', async () => {
    const zipBuffer = new ArrayBuffer(16)
    mocks.getDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=1')
    mocks.getFileFromBucket.mockResolvedValue(zipBuffer)
    const wrapper = mount(Harness)
    const zipped = { id: 'z', name: 'z', file_index: { 'exp.db.zip': [512, 16] } }
    const raw = { id: 'r', name: 'r', file_index: { 'exp.db': [1024, 32768] } }
    const initialized = init([zipped, raw] as unknown as ModelArtifact[])
    await vi.waitFor(() => expect(workers[0].postMessage).toHaveBeenCalled())

    const [message] = workers[0].postMessage.mock.calls[0]
    expect(message.payload).toEqual([
      { modelId: 'z', source: { kind: 'zip', buffer: zipBuffer } },
      {
        modelId: 'r',
        source: { kind: 'range', url: 'https://bucket/artifact?sig=1', offset: 1024, size: 32768 },
      },
    ])
    expect(mocks.getFileFromBucket).toHaveBeenCalledOnce()
    workers[0].emit({ type: 'result', requestId: message.requestId, data: true })
    await initialized
    wrapper.unmount()
  })

  it('renews the presigned URL through the artifacts store for the worker proxy', async () => {
    mocks.getDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=1')
    mocks.renewDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=2')
    const wrapper = mount(Harness)
    const raw = { id: 'r', name: 'r', file_index: { 'exp.db': [1024, 32768] } }
    const initialized = init([raw] as unknown as ModelArtifact[])
    await vi.waitFor(() => expect(workers[0].postMessage).toHaveBeenCalled())
    const [first] = workers[0].postMessage.mock.calls[0]
    workers[0].emit({
      type: 'result',
      requestId: first.requestId,
      data: [{ modelId: 'r', error: { code: SNAPSHOT_SOURCE_EXPIRED, message: 'expired' } }],
    })
    await vi.waitFor(() => expect(workers[0].postMessage).toHaveBeenCalledTimes(2))

    const [reopen] = workers[0].postMessage.mock.calls[1]
    expect(mocks.downloadUrlSource).toHaveBeenCalledWith('r')
    expect(mocks.renewDownloadUrl).toHaveBeenCalledExactlyOnceWith('https://bucket/artifact?sig=1')
    expect(reopen).toMatchObject({
      type: 'reopen',
      payload: { modelId: 'r', source: { url: 'https://bucket/artifact?sig=2' } },
    })
    workers[0].emit({ type: 'result', requestId: reopen.requestId, data: [] })
    await initialized
    wrapper.unmount()
  })

  async function sentPayload(models: unknown[]) {
    const initialized = init(models as ModelArtifact[])
    await vi.waitFor(() => expect(workers[0].postMessage).toHaveBeenCalled())
    const [message] = workers[0].postMessage.mock.calls[0]
    workers[0].emit({ type: 'result', requestId: message.requestId, data: [] })
    await initialized
    return message.payload
  }

  it('opens the others when one download fails, and reports it without the URL or token', async () => {
    const zipBuffer = new ArrayBuffer(16)
    mocks.getDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=SECRET')
    mocks.getFileFromBucket
      .mockRejectedValueOnce(
        Object.assign(new Error("Failed to load 'https://bucket/artifact?sig=SECRET'"), {
          name: 'AxiosError',
          config: {
            url: 'https://bucket/artifact?sig=SECRET',
            headers: { Authorization: 'SECRET' },
          },
        }),
      )
      .mockResolvedValueOnce(zipBuffer)
    const wrapper = mount(Harness)
    const failing = { id: 'z1', name: 'z1', file_index: { 'exp.db.zip': [512, 16] } }
    const working = { id: 'z2', name: 'z2', file_index: { 'exp.db.zip': [512, 16] } }

    const payload = await sentPayload([failing, working])

    expect(payload).toEqual([
      { modelId: 'z1', error: { code: READ_FAILED, message: "Failed to load 'https://bucket'" } },
      { modelId: 'z2', source: { kind: 'zip', buffer: zipBuffer } },
    ])
    expect(JSON.stringify(payload)).not.toContain('SECRET')
    expect(mocks.setExperimentSnapshotProvider).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('does not download with a header other than Authorization', async () => {
    mocks.getDownloadUrl.mockResolvedValue({
      url: 'https://workspace.test/a.tar',
      headers: { 'X-Api-Key': 'SECRET' },
    })
    const wrapper = mount(Harness)
    const zipped = { id: 'z', name: 'z', file_index: { 'exp.db.zip': [512, 16] } }

    const payload = await sentPayload([zipped])

    expect(mocks.getFileFromBucket).not.toHaveBeenCalled()
    expect(payload).toEqual([
      { modelId: 'z', error: expect.objectContaining({ code: READ_FAILED }) },
    ])
    expect(JSON.stringify(payload)).not.toContain('SECRET')
    wrapper.unmount()
  })

  it('passes the headers of a location that needs them into the range source', async () => {
    const location = {
      url: 'https://workspace.test/api/2.0/fs/files/a.tar',
      headers: { Authorization: 'Bearer t1' },
    }
    mocks.getDownloadUrl.mockResolvedValue(location)
    const wrapper = mount(Harness)
    const raw = { id: 'r', name: 'r', file_index: { 'exp.db': [1024, 32768] } }
    const initialized = init([raw] as unknown as ModelArtifact[])
    await vi.waitFor(() => expect(workers[0].postMessage).toHaveBeenCalled())

    const [message] = workers[0].postMessage.mock.calls[0]
    expect(message.payload).toEqual([
      { modelId: 'r', source: { kind: 'range', ...location, offset: 1024, size: 32768 } },
    ])
    workers[0].emit({ type: 'result', requestId: message.requestId, data: true })
    await initialized
    wrapper.unmount()
  })

  it('fails a zip whose directory is too large without downloading it, and opens the others', async () => {
    const tail = zipDirectoryTail(3_811_495_936)
    fetchMock.mockResolvedValueOnce(new Response(tail.slice(), { status: 206 }))
    const zipBuffer = new ArrayBuffer(16)
    mocks.getDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=SECRET')
    mocks.getFileFromBucket.mockResolvedValue(zipBuffer)
    const wrapper = mount(Harness)
    const huge = { id: 'big', name: 'big', file_index: { 'exp.db.zip': [512, ZIP_MEMBER_SIZE] } }
    const small = { id: 'small', name: 'small', file_index: { 'exp.db.zip': [4096, 16] } }

    const payload = await sentPayload([huge, small])

    expect(payload).toEqual([
      {
        modelId: 'big',
        error: { code: SNAPSHOT_TOO_LARGE_FOR_BROWSER, message: expect.any(String) },
      },
      { modelId: 'small', source: { kind: 'zip', buffer: zipBuffer } },
    ])
    expect(JSON.stringify(payload)).not.toContain('SECRET')
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get('Range')).toBe(
      `bytes=${512 + ZIP_MEMBER_SIZE - ZIP_TAIL_BYTES}-${512 + ZIP_MEMBER_SIZE - 1}`,
    )
    expect(mocks.getFileFromBucket).toHaveBeenCalledOnce()
    expect(mocks.getFileFromBucket.mock.calls[0]?.[1]).toBe('exp.db.zip')
    wrapper.unmount()
  })

  it('downloads a zip once after its directory shows that it fits', async () => {
    const tail = zipDirectoryTail(5000)
    fetchMock.mockResolvedValueOnce(new Response(tail.slice(), { status: 206 }))
    const zipBuffer = new ArrayBuffer(16)
    mocks.getDownloadUrl.mockResolvedValue('https://bucket/artifact?sig=1')
    mocks.getFileFromBucket.mockResolvedValue(zipBuffer)
    const wrapper = mount(Harness)
    const zipped = { id: 'z', name: 'z', file_index: { 'exp.db.zip': [512, ZIP_MEMBER_SIZE] } }

    const payload = await sentPayload([zipped])

    expect(payload).toEqual([{ modelId: 'z', source: { kind: 'zip', buffer: zipBuffer } }])
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(mocks.getFileFromBucket).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})
