import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useArtifactsStore } from '@/stores/artifacts'

const mocks = vi.hoisted(() => ({ download: vi.fn(), url: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org', id: 'orbit', collectionId: 'collection' } }),
}))
vi.mock('@/lib/api', () => ({ api: { artifacts: { getDownloadUrl: mocks.url } } }))
vi.mock('@/helpers/helpers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/helpers/helpers')>()),
  downloadFileFromBlob: mocks.download,
}))
beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mocks.url.mockResolvedValue({ url: 'https://example.test/model' })
})
afterEach(() => vi.unstubAllGlobals())
it.each([403, 404, 500])('rejects HTTP %s without saving the error body', async (status) => {
  const blob = vi.fn().mockResolvedValue(new Blob(['AccessDenied']))
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, blob }))
  await expect(useArtifactsStore().downloadArtifact('artifact', 'model.fnnx')).rejects.toThrow(
    'Failed to download artifact',
  )
  expect(blob).not.toHaveBeenCalled()
  expect(mocks.download).not.toHaveBeenCalled()
})
it('saves a successful download with its requested name', async () => {
  const blob = new Blob(['model'])
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => blob }))
  await useArtifactsStore().downloadArtifact('artifact', 'model.fnnx')
  expect(mocks.download).toHaveBeenCalledWith(blob, 'model.fnnx')
})
