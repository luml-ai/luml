import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Orbit, OrbitPermissions, OrganizationDetails } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '../organization'
import { useOrbitsStore } from '../orbits'

const apiMocks = vi.hoisted(() => ({
  getOrganizationOrbits: vi.fn(),
  updateOrbit: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))

const ORGANIZATION_ID = 'organization-1'
const permissions = { orbit: ['read', 'update', 'delete'] } as unknown as OrbitPermissions
const savedOrbit = {
  id: 'orbit-1',
  name: 'Old name',
  organization_id: ORGANIZATION_ID,
  total_collections: 3,
  permissions,
} as Orbit
const otherOrbit = { id: 'orbit-2', name: 'Other', permissions } as Orbit

describe('updating an orbit', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    apiMocks.getOrganizationOrbits.mockResolvedValue([savedOrbit, otherOrbit])
    await useOrbitsStore().loadOrbitsList(ORGANIZATION_ID)
    useOrganizationStore().organizationDetails = {
      orbits: [savedOrbit, otherOrbit],
    } as unknown as OrganizationDetails
  })

  it('keeps the listed permissions when the response has none', async () => {
    apiMocks.updateOrbit.mockResolvedValue({
      id: savedOrbit.id,
      name: 'New name',
      permissions: null,
    })
    const orbitsStore = useOrbitsStore()

    await orbitsStore.updateOrbit(ORGANIZATION_ID, { id: savedOrbit.id, name: 'New name' })

    const updated = orbitsStore.orbitsList.find((orbit) => orbit.id === savedOrbit.id)
    expect(updated).toMatchObject({ name: 'New name', total_collections: 3, permissions })
    expect(useOrganizationStore().organizationDetails?.orbits[0]).toMatchObject({
      name: 'New name',
      permissions,
    })
    expect(orbitsStore.orbitsList[1]).toEqual(otherOrbit)
  })

  it('takes the permissions from the response when it has them', async () => {
    const narrowed = { orbit: ['read'] } as unknown as OrbitPermissions
    apiMocks.updateOrbit.mockResolvedValue({ ...savedOrbit, permissions: narrowed })
    const orbitsStore = useOrbitsStore()

    await orbitsStore.updateOrbit(ORGANIZATION_ID, { id: savedOrbit.id, name: savedOrbit.name })

    expect(orbitsStore.orbitsList[0].permissions).toEqual(narrowed)
  })
})
