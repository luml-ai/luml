import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, expect, it, vi } from 'vitest'
import OrbitCreator from './OrbitCreator.vue'

const stores = vi.hoisted(() => ({ orbits: { orbitsList: [] as { id: string; name: string }[] } }))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => reactive(stores.orbits) }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => ({}) }))
vi.mock('@/stores/buckets', () => ({ useBucketsStore: () => ({ buckets: [] }) }))
vi.mock('@/stores/relays', () => ({ useRelaysStore: () => ({ relays: [] }) }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({}) }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
beforeEach(() => {
  stores.orbits.orbitsList = []
})
it('validates names against orbit lists loaded after the creator mounts', async () => {
  const wrapper = shallowMount(OrbitCreator, {
    props: { organizationId: 'org', visible: true },
    global: { renderStubDefaultSlot: true },
  })
  const resolverBeforeLoad = (
    wrapper.vm as unknown as {
      resolver: (args: object) => Promise<{ errors: Record<string, unknown[]> }>
    }
  ).resolver
  reactive(stores.orbits).orbitsList = [{ id: 'o1', name: 'Existing Orbit' }]
  await flushPromises()
  const resolver = (
    wrapper.vm as unknown as {
      resolver: (args: object) => Promise<{ errors: Record<string, unknown[]> }>
    }
  ).resolver
  const result = await resolver({
    values: { name: 'Existing Orbit', members: [], bucket_secret_id: 'bucket' },
  })
  expect(result.errors.name).toEqual([
    expect.objectContaining({ message: 'An Orbit with this name already exists' }),
  ])
  const valid = await resolverBeforeLoad({
    values: { name: 'Another Orbit', members: [], bucket_secret_id: 'bucket' },
  })
  expect(valid.errors).toEqual({})
  wrapper.unmount()
})
