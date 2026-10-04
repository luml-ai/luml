import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import OrganizationOrbits from './OrganizationOrbits.vue'

const getOrbitDetails = vi.hoisted(() => vi.fn())
const toastAdd = vi.hoisted(() => vi.fn())
const organizationStore = vi.hoisted(() => ({
  currentOrganization: { id: 'org-1', permissions: { orbit: [] as string[] } },
  organizationDetails: {
    orbits: [{ id: 'orbit-1', name: 'Research', total_members: 2, created_at: '2026-10-01' }],
  },
}))

vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({ getOrbitDetails }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: toastAdd }),
}))

const OrbitEditorStub = {
  name: 'OrbitEditor',
  props: ['visible', 'orbit'],
  template: '<div v-if="visible" class="orbit-editor">{{ orbit.name }}</div>',
}

const stubs = {
  Button: {
    props: ['loading'],
    emits: ['click'],
    template: '<button @click="$emit(\'click\')"><slot name="icon" /><slot /></button>',
  },
  OrganizationOrbitSettings: true,
  OrbitCreator: true,
  OrbitEditor: OrbitEditorStub,
}

function mountTab(orbitPermissions: string[]) {
  organizationStore.currentOrganization.permissions.orbit = orbitPermissions
  return mount(OrganizationOrbits, { global: { stubs } })
}

describe('OrganizationOrbits', () => {
  beforeEach(() => {
    getOrbitDetails.mockReset()
    toastAdd.mockReset()
  })

  it('opens the orbit settings with the loaded orbit details', async () => {
    getOrbitDetails.mockResolvedValue({ id: 'orbit-1', name: 'Research', relay_id: null })
    const wrapper = mountTab([PermissionEnum.update])

    await wrapper.get('[aria-label="Orbit settings"]').trigger('click')
    await flushPromises()

    expect(getOrbitDetails).toHaveBeenCalledWith('org-1', 'orbit-1')
    expect(wrapper.get('.orbit-editor').text()).toBe('Research')
  })

  it('hides the orbit settings without the permission to update orbits', () => {
    const wrapper = mountTab([PermissionEnum.create])

    expect(wrapper.find('[aria-label="Orbit settings"]').exists()).toBe(false)
  })

  it('shows an error when the orbit details fail to load', async () => {
    getOrbitDetails.mockRejectedValue(new Error('boom'))
    const wrapper = mountTab([PermissionEnum.update])

    await wrapper.get('[aria-label="Orbit settings"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('.orbit-editor').exists()).toBe(false)
    expect(toastAdd).toHaveBeenCalledOnce()
  })
})
