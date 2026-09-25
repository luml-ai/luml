import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useExperimentSnapshotsDatabaseProvider } from './useExperimentSnapshotsDatabaseProvider'

const mocks = vi.hoisted(() => ({
  getDownloadUrl: vi.fn(),
  setExperimentSnapshotProvider: vi.fn(),
  getFileFromBucket: vi.fn(),
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
  FnnxService: { findExperimentSnapshotArchiveName: () => 'snapshot' },
}))

vi.mock('@luml/experiments', () => ({
  ExperimentSnapshotWorkerProxy: class {
    constructor(public worker: Worker) {}
  },
}))

class MockWorker {
  readonly terminate = vi.fn()
  readonly postMessage = vi.fn()
  readonly listeners = new Set<(event: MessageEvent) => void>()

  addEventListener(_type: string, listener: (event: MessageEvent) => void) {
    this.listeners.add(listener)
  }

  removeEventListener(_type: string, listener: (event: MessageEvent) => void) {
    this.listeners.delete(listener)
  }

  emit(data: unknown) {
    this.listeners.forEach((listener) => listener({ data } as MessageEvent))
  }
}

let init: ReturnType<typeof useExperimentSnapshotsDatabaseProvider>['init']
let workers: MockWorker[]

const Harness = defineComponent({
  setup() {
    init = useExperimentSnapshotsDatabaseProvider().init
    return () => h('div')
  },
})

describe('experiment snapshot worker lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workers = []
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

  it('terminates the worker when the view unmounts after initialization', async () => {
    const wrapper = mount(Harness)
    const initialized = init([])
    await Promise.resolve()

    const worker = workers[0]
    const message = worker.postMessage.mock.calls[0][0]
    worker.emit({ requestId: message.requestId, data: null })
    await initialized

    expect(mocks.setExperimentSnapshotProvider).toHaveBeenCalledOnce()
    wrapper.unmount()
    expect(worker.terminate).toHaveBeenCalledOnce()
  })

  it('settles an in-flight worker request and removes its listener on unmount', async () => {
    const wrapper = mount(Harness)
    const initialized = init([])
    const rejection = expect(initialized).rejects.toThrow('unmounted')
    await Promise.resolve()

    const worker = workers[0]
    expect(worker.postMessage).toHaveBeenCalledOnce()
    wrapper.unmount()

    await rejection
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
})
