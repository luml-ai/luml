import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OrganizationRegistry from './OrganizationRegistry.vue'

const mocks = vi.hoisted(() => ({ getBucketSecretsList: vi.fn(), toast: vi.fn() }))

vi.mock('@/lib/api', () => ({
  api: { bucketSecrets: { getBucketSecretsList: mocks.getBucketSecretsList } },
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: { id: 'org' } }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))

const bucket = {
  id: 'bucket-1',
  bucket_name: 'previous-bucket',
  endpoint: 'storage.example.com',
  created_at: '2026-11-01T00:00:00Z',
}

function mountRegistry() {
  return mount(OrganizationRegistry, {
    global: {
      stubs: { OrganizationBucketCreator: true, BucketSettings: true, UiPageLoader: true },
    },
  })
}

enableAutoUnmount(afterEach)

describe('organization buckets page', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('drops the rows and the count of the previous load when a reload fails', async () => {
    mocks.getBucketSecretsList.mockResolvedValueOnce([bucket])
    const loaded = mountRegistry()
    await flushPromises()
    expect(loaded.text()).toContain('previous-bucket')
    expect(loaded.text()).toContain('(1)')
    loaded.unmount()

    mocks.getBucketSecretsList.mockRejectedValueOnce(new Error('Buckets unavailable'))
    const failed = mountRegistry()
    await flushPromises()

    expect(failed.text()).toContain('Failed to load buckets.')
    expect(failed.text()).toContain('(0)')
    expect(failed.text()).not.toContain('previous-bucket')
    expect(failed.text()).not.toContain('No buckets created')
    expect(mocks.toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Buckets unavailable' }),
    )
  })

  it('shows the rows again after a successful reload', async () => {
    mocks.getBucketSecretsList.mockRejectedValueOnce(new Error('Buckets unavailable'))
    const failed = mountRegistry()
    await flushPromises()
    failed.unmount()

    mocks.getBucketSecretsList.mockResolvedValueOnce([bucket])
    const reloaded = mountRegistry()
    await flushPromises()

    expect(reloaded.text()).toContain('previous-bucket')
    expect(reloaded.text()).not.toContain('Failed to load buckets.')
  })
})
