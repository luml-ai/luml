import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'

const apiMocks = vi.hoisted(() => ({
  getDownloadUrl: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    artifacts: {
      getDownloadUrl: apiMocks.getDownloadUrl,
    },
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { organizationId: 'org', id: 'orbit', collectionId: 'collection' },
  }),
}))

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

import { useArtifactsStore } from '@/stores/artifacts'

const mockedAxios = vi.mocked(axios)

function artifact(id = 'model'): Artifact {
  return {
    id,
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.uploaded,
    size: 200,
    file_index: {
      'attachments.tar': [0, 100],
      'attachments.index.json': [100, 50],
    },
  } as Artifact
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('artifact attachment loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getDownloadUrl.mockReset()
    mockedAxios.get.mockReset()
    apiMocks.getDownloadUrl.mockResolvedValue({ url: 'https://download.test/model' })
  })

  it('caches the downloaded index and downloader for the attachments view', async () => {
    mockedAxios.get.mockResolvedValue({
      data: { 'attachments/report.pdf': [0, 42] },
    })
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('available')
    expect(store.attachmentsIndex).toEqual({ 'attachments/report.pdf': [0, 42] })
    expect(store.attachmentsDownloader).not.toBeNull()
    expect(mockedAxios.get).toHaveBeenCalledTimes(1)
  })

  it('marks an empty parsed index as empty', async () => {
    mockedAxios.get.mockResolvedValue({ data: { 'attachments/': [0, 0] } })
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('empty')
    expect(store.attachmentsIndex).toBeNull()
  })

  it('keeps an error state when the download URL request fails', async () => {
    apiMocks.getDownloadUrl.mockRejectedValue(new Error('url unavailable'))
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('error')
    expect(store.attachmentsError).toContain('url unavailable')
    expect(mockedAxios.get).not.toHaveBeenCalled()
  })

  it('keeps an error state when the attachment index request fails', async () => {
    mockedAxios.get.mockRejectedValue(new Error('range unavailable'))
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('error')
    expect(store.attachmentsError).toContain('range unavailable')
  })

  it('rejects malformed attachment index content', async () => {
    mockedAxios.get.mockResolvedValue({ data: { 'attachments/report.pdf': [90, 42] } })
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('error')
    expect(store.attachmentsError).toContain('invalid content')
  })

  it('rejects an oversized attachment index before requesting it', async () => {
    const store = useArtifactsStore()
    const model = artifact()
    model.size = 2_000_000
    model.file_index['attachments.index.json'] = [100, 1_048_577]
    store.setCurrentArtifact(model)

    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('error')
    expect(store.attachmentsError).toContain('invalid range')
    expect(apiMocks.getDownloadUrl).not.toHaveBeenCalled()
  })

  it('ignores stale results after navigating to another artifact', async () => {
    const firstUrl = deferred<{ url: string }>()
    apiMocks.getDownloadUrl.mockImplementation((...args: unknown[]) => {
      return args.at(-1) === 'first'
        ? firstUrl.promise
        : Promise.resolve({ url: 'https://download.test/second' })
    })
    mockedAxios.get.mockImplementation((url) => {
      return Promise.resolve({
        data: url === 'https://download.test/first' ? { 'attachments/report.pdf': [0, 42] } : {},
      })
    })
    const store = useArtifactsStore()
    const first = artifact('first')
    const second = artifact('second')
    store.setCurrentArtifact(first)
    const firstLoad = store.loadCurrentArtifactAttachments(first)

    store.setCurrentArtifact(second)
    await store.loadCurrentArtifactAttachments(second)
    firstUrl.resolve({ url: 'https://download.test/first' })
    await firstLoad

    expect(store.currentArtifact?.id).toBe('second')
    expect(store.attachmentsStatus).toBe('empty')
    expect(store.attachmentsIndex).toBeNull()
  })

  it('can retry after an inspection failure', async () => {
    apiMocks.getDownloadUrl.mockRejectedValueOnce(new Error('temporary failure'))
    mockedAxios.get.mockResolvedValue({
      data: { 'attachments/report.pdf': [0, 42] },
    })
    const store = useArtifactsStore()
    const model = artifact()
    store.setCurrentArtifact(model)
    await store.loadCurrentArtifactAttachments(model)
    await store.loadCurrentArtifactAttachments(model)

    expect(store.attachmentsStatus).toBe('available')
    expect(apiMocks.getDownloadUrl).toHaveBeenCalledTimes(2)
  })
})
