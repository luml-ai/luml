import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Organization } from '@/lib/api/api.interfaces'
import { BucketTypeEnum, type BucketSecret } from '@/lib/api/bucket-secrets/interfaces'
import { useOrganizationStore } from '@/stores/organization'
import OrganizationRegistryTable from './OrganizationRegistryTable.vue'

const { getBucketSecretsList } = vi.hoisted(() => ({ getBucketSecretsList: vi.fn() }))

vi.mock('@/lib/api', () => ({
  api: { bucketSecrets: { getBucketSecretsList } },
}))

vi.mock('./BucketSettings.vue', () => ({ default: { template: '<span />' } }))

function bucket(organizationId: string): BucketSecret {
  return {
    id: `bucket-${organizationId}`,
    organization_id: organizationId,
    bucket_name: `${organizationId} bucket`,
    endpoint: `${organizationId}.example.com`,
    type: BucketTypeEnum.s3,
    secure: true,
    region: '',
    cert_check: true,
    created_at: new Date(),
    updated_at: new Date(),
    orbits: [],
  }
}

function deferredBuckets() {
  let resolve!: (buckets: BucketSecret[]) => void
  const promise = new Promise<BucketSecret[]>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('OrganizationRegistryTable', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    const organizations = useOrganizationStore()
    organizations.availableOrganizations = [{ id: 'A' }, { id: 'B' }] as Organization[]
    organizations.setCurrentOrganizationId('A')
  })

  it('loads the selected organization and replaces its buckets when the organization changes', async () => {
    const nextBuckets = deferredBuckets()
    getBucketSecretsList
      .mockResolvedValueOnce([bucket('A')])
      .mockReturnValueOnce(nextBuckets.promise)
    const wrapper = mount(OrganizationRegistryTable)
    await flushPromises()
    expect(wrapper.text()).toContain('A bucket')

    useOrganizationStore().setCurrentOrganizationId('B')
    await flushPromises()
    expect(getBucketSecretsList).toHaveBeenCalledWith('B')
    expect(wrapper.text()).not.toContain('A bucket')

    nextBuckets.resolve([bucket('B')])
    await flushPromises()
    expect(wrapper.text()).toContain('B bucket')
    expect(wrapper.text()).not.toContain('A bucket')
  })

  it('ignores an older organization response that arrives after the new one', async () => {
    const oldBuckets = deferredBuckets()
    const newBuckets = deferredBuckets()
    getBucketSecretsList
      .mockReturnValueOnce(oldBuckets.promise)
      .mockReturnValueOnce(newBuckets.promise)
    const wrapper = mount(OrganizationRegistryTable)

    useOrganizationStore().setCurrentOrganizationId('B')
    await flushPromises()
    newBuckets.resolve([bucket('B')])
    await flushPromises()
    oldBuckets.resolve([bucket('A')])
    await flushPromises()

    expect(wrapper.text()).toContain('B bucket')
    expect(wrapper.text()).not.toContain('A bucket')
  })

  it('clears buckets when there is no current organization', async () => {
    getBucketSecretsList.mockResolvedValue([bucket('A')])
    const wrapper = mount(OrganizationRegistryTable)
    await flushPromises()

    useOrganizationStore().resetCurrentOrganization()
    await flushPromises()
    expect(wrapper.text()).not.toContain('A bucket')
    expect(wrapper.text()).toContain('No buckets created')
  })
})
