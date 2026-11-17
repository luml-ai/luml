import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import axios from 'axios'
import { useArtifactsStore } from '@/stores/artifacts'
import { useDatasetsStore } from '@/stores/datasets'
import { ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import { formatCellValue } from '@/components/table-view/index.vue'
import { PresignedUrlCache } from '@/lib/bucket-service/presigned-url-cache'

vi.mock('@/lib/api', () => ({ api: {} }))
vi.mock('axios', () => ({ default: { get: vi.fn() } }))
vi.mock('@/utils/ParquetHandler', () => ({ ParquetHandler: vi.fn() }))
const toast = vi.hoisted(() => ({ add: vi.fn() }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => toast,
}))

const csvText = (value: string) => `col\n${value}`
// Every test body but one is a five-character value; a chunk's range is its body's length.
const CHUNK_LENGTH = csvText('value').length

async function setup(chunkLength = CHUNK_LENGTH) {
  const artifacts = useArtifactsStore()
  artifacts.currentArtifact = {
    id: 'dataset',
    type: ArtifactTypeEnum.dataset,
    file_index: { c0: [0, chunkLength], c1: [chunkLength, chunkLength] },
    manifest: {
      payload: {
        subsets: { main: { splits: { train: { chunk_files: ['c0', 'c1'], file_format: 'csv' } } } },
      },
    },
  } as unknown as Artifact
  const getDownloadUrl = vi
    .fn<(id: string) => Promise<string>>()
    .mockResolvedValueOnce('https://bucket/first')
    .mockResolvedValue('https://bucket/refreshed')
  const urls = new PresignedUrlCache(getDownloadUrl)
  vi.spyOn(artifacts, 'downloadUrlSource').mockImplementation((id) => urls.source(id))
  const store = useDatasetsStore()
  await store.init()
  store.setSelectedSubset('main')
  store.setSelectedSplit('train')
  await flushPromises()
  return { store, getDownloadUrl }
}
const csv = (value: string) => ({ data: new TextEncoder().encode(csvText(value)).buffer })
beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(axios.get).mockReset()
})
describe('dataset paging', () => {
  it('preserves date-only CSV days when rendering downloaded dataset rows', async () => {
    const rows = '2024-01-01\n2023-12-31T19:00'
    vi.mocked(axios.get).mockResolvedValue(csv(rows))
    const { store } = await setup(csvText(rows).length)
    store.setCurrentPage(0)
    await flushPromises()

    expect(store.tableRows.map((row) => formatCellValue(row.col))).toEqual([
      '2024-01-01',
      '2023-12-31 19:00',
    ])
  })
  it('reuses the presigned URL for subsequent chunks', async () => {
    vi.mocked(axios.get).mockResolvedValue(csv('value'))
    const { store, getDownloadUrl } = await setup()
    store.setCurrentPage(0)
    await flushPromises()
    store.setCurrentPage(1)
    await flushPromises()
    expect(getDownloadUrl).toHaveBeenCalledOnce()
    expect(axios.get).toHaveBeenLastCalledWith('https://bucket/first', expect.anything())
  })
  it('renews the presigned URL once and retries a chunk read that fails', async () => {
    vi.mocked(axios.get).mockRejectedValueOnce(new Error('403')).mockResolvedValue(csv('value'))
    const { store, getDownloadUrl } = await setup()
    store.setCurrentPage(0)
    await flushPromises()
    expect(getDownloadUrl).toHaveBeenCalledTimes(2)
    expect(vi.mocked(axios.get).mock.calls.map(([url]) => url)).toEqual([
      'https://bucket/first',
      'https://bucket/refreshed',
    ])
    expect(store.tableRows.map((row) => row.col)).toEqual(['value'])
  })
  it.each(['resolve', 'reject'])(
    'keeps the latest page when the old page %ss late',
    async (settle) => {
      let resolveOld!: (value: ReturnType<typeof csv>) => void
      let rejectOld!: (error: Error) => void
      vi.mocked(axios.get)
        .mockReturnValueOnce(
          new Promise((resolve, reject) => {
            resolveOld = resolve
            rejectOld = reject
          }),
        )
        .mockResolvedValueOnce(csv('page1'))
      const { store } = await setup()
      store.setCurrentPage(0)
      await flushPromises()
      store.setCurrentPage(1)
      await flushPromises()
      if (settle === 'resolve') resolveOld(csv('page0'))
      else rejectOld(new Error('Expired request'))
      await flushPromises()
      expect(store.tableRows).toEqual([{ col: 'page1' }])
      expect(toast.add).not.toHaveBeenCalled()
    },
  )
  it('does not repopulate rows after resetting an in-flight dataset', async () => {
    let resolveOld!: (value: ReturnType<typeof csv>) => void
    vi.mocked(axios.get).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOld = resolve
      }),
    )
    const { store } = await setup()
    store.setCurrentPage(0)
    await flushPromises()
    store.reset()
    resolveOld(csv('stale'))
    await flushPromises()
    expect(store.tableRows).toEqual([])
    expect(store.isInitialized).toBe(false)
    expect(toast.add).not.toHaveBeenCalled()
  })
})
