import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import OrbitManagePopover from './OrbitManagePopover.vue'

const orbitStore = reactive({
  currentOrbit: { id: 'orbit-1', name: 'Orbit' },
  currentOrbitDetails: { total_collections: 0 },
  orbitsList: [],
})

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => orbitStore }))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: null, organizationDetails: null }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ name: 'orbit-collections', params: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

describe('OrbitManagePopover count label', () => {
  it.each([
    [0, '0 collections'],
    [1, '1 collection'],
    [2, '2 collections'],
  ])('renders %s collections as %s', (count, label) => {
    orbitStore.currentOrbitDetails.total_collections = count

    const wrapper = mount(OrbitManagePopover, {
      global: {
        directives: { tooltip: () => undefined },
        stubs: {
          Popover: { template: '<div><slot /></div>' },
          OrbitCreator: true,
          OrbitEditor: true,
          UiId: true,
          'd-button': true,
        },
      },
    })

    expect(wrapper.get('.collections-count').text()).toBe(label)
  })
})
