import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import OrganizationOrbits from './OrganizationOrbits.vue'
import { OrganizationRoleEnum } from './organization.interfaces'

const getOrbitDetails = vi.hoisted(() => vi.fn())
const toastAdd = vi.hoisted(() => vi.fn())
const organizationStore = vi.hoisted(() => ({
  currentOrganization: {
    id: 'org-1',
    role: 'member' as string,
    permissions: { orbit: ['create'] as string[] },
  },
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

function mountTab(
  role: OrganizationRoleEnum,
  orbitPermissions: string[] = [PermissionEnum.create],
) {
  organizationStore.currentOrganization.role = role
  organizationStore.currentOrganization.permissions.orbit = orbitPermissions
  return mount(OrganizationOrbits, { global: { stubs } })
}

describe('OrganizationOrbits', () => {
  beforeEach(() => {
    getOrbitDetails.mockReset()
    toastAdd.mockReset()
  })

  it.each([OrganizationRoleEnum.owner, OrganizationRoleEnum.admin])(
    'opens the orbit settings with the loaded orbit details for an %s',
    async (role) => {
      getOrbitDetails.mockResolvedValue({ id: 'orbit-1', name: 'Research', relay_id: null })
      const wrapper = mountTab(role)

      await wrapper.get('[aria-label="Orbit settings"]').trigger('click')
      await flushPromises()

      expect(getOrbitDetails).toHaveBeenCalledWith('org-1', 'orbit-1')
      expect(wrapper.get('.orbit-editor').text()).toBe('Research')
    },
  )

  it('hides the orbit settings from a member', () => {
    const wrapper = mountTab(OrganizationRoleEnum.member)

    expect(wrapper.find('[aria-label="Orbit settings"]').exists()).toBe(false)
  })

  it.each([
    [[PermissionEnum.create], true],
    [[], false],
  ])('shows the create button by the create permission %j', (orbitPermissions, shown) => {
    const wrapper = mountTab(OrganizationRoleEnum.member, orbitPermissions)

    expect(wrapper.text().includes('New Orbit')).toBe(shown)
  })

  it('shows an error when the orbit details fail to load', async () => {
    getOrbitDetails.mockRejectedValue(new Error('boom'))
    const wrapper = mountTab(OrganizationRoleEnum.admin)

    await wrapper.get('[aria-label="Orbit settings"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('.orbit-editor').exists()).toBe(false)
    expect(toastAdd).toHaveBeenCalledOnce()
  })
})
