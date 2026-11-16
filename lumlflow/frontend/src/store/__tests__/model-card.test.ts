import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useModelCardStore } from '@/store/model-card'
const { apiService, revoke } = vi.hoisted(() => ({
  apiService: { getModel: vi.fn(), getModelCard: vi.fn() },
  revoke: vi.fn(),
}))
vi.mock('@/api/api.service', () => ({ apiService }))
vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/components/model-card/model-card.utils', () => ({
  extractHtmlFromModelCardZip: vi.fn().mockResolvedValue('<html/>'),
  createHtmlBlobUrl: vi.fn().mockReturnValue('blob:card'),
}))
beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.stubGlobal('URL', { revokeObjectURL: revoke })
  apiService.getModel.mockResolvedValue({ id: 'model' })
  apiService.getModelCard.mockResolvedValue(new Blob())
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
it('starts loading immediately and revokes URLs on reopen and close', async () => {
  vi.useFakeTimers()
  const store = useModelCardStore()
  const request = store.showModelCard('model')
  expect(apiService.getModel).toHaveBeenCalledWith('model')
  await request
  expect(store.modelCardHtmlUrl).toBe('blob:card')
  await store.showModelCard('model')
  expect(revoke).toHaveBeenCalledTimes(1)
  store.hideModelCard()
  expect(revoke).toHaveBeenCalledTimes(2)
  expect(store.modelCardHtmlUrl).toBeNull()
})
