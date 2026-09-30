import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Orbit, Organization, OrganizationDetails } from '@/lib/api/api.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { useOrganizationStore } from '../organization'
import { useOrbitsStore } from '../orbits'

const apiMocks = vi.hoisted(() => ({
  leaveOrganization: vi.fn(),
  getOrganization: vi.fn(),
  getOrganizationOrbits: vi.fn(),
  getOrbitDetails: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))

const firstOrganization = { id: 'organization-1', name: 'First' } as Organization
const secondOrganization = { id: 'organization-2', name: 'Second' } as Organization
const firstOrbit = { id: 'orbit-1', organization_id: firstOrganization.id } as Orbit
const secondOrbit = { id: 'orbit-2', organization_id: secondOrganization.id } as Orbit

describe('leaving an organization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    apiMocks.leaveOrganization.mockResolvedValue(undefined)
    apiMocks.getOrganization.mockImplementation(async (id: string) => ({ id }))
    apiMocks.getOrganizationOrbits.mockResolvedValue([secondOrbit])
    apiMocks.getOrbitDetails.mockResolvedValue({ id: secondOrbit.id })
  })

  function selectedOrganization() {
    const store = useOrganizationStore()
    store.availableOrganizations = [firstOrganization, secondOrganization]
    store.setCurrentOrganizationId(firstOrganization.id)
    store.organizationDetails = { id: firstOrganization.id } as OrganizationDetails
    const orbits = useOrbitsStore()
    orbits.orbitsList = [firstOrbit]
    orbits.setCurrentOrbitId(firstOrbit.id)
    return { store, orbits }
  }

  it('selects a remaining organization and its orbit and persists the replacement', async () => {
    const { store, orbits } = selectedOrganization()

    await store.leaveOrganization(firstOrganization.id)

    expect(apiMocks.leaveOrganization).toHaveBeenCalledWith(firstOrganization.id)
    expect(store.availableOrganizations).toEqual([secondOrganization])
    expect(store.currentOrganization?.id).toBe(secondOrganization.id)
    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(orbits.currentOrbitId).toBe(secondOrbit.id)
    expect(LocalStorageService.get('currentOrganizationId')).toBe(secondOrganization.id)
    expect(LocalStorageService.get('currentOrbitId')).toBe(secondOrbit.id)
    expect(apiMocks.getOrganizationOrbits).toHaveBeenCalledWith(secondOrganization.id)
  })

  it('clears organization and orbit state and storage when no organizations remain', async () => {
    const { store, orbits } = selectedOrganization()
    store.availableOrganizations = [firstOrganization]

    await store.leaveOrganization(firstOrganization.id)

    expect(store.availableOrganizations).toEqual([])
    expect(store.currentOrganization).toBeNull()
    expect(store.organizationDetails).toBeNull()
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitId).toBeNull()
    expect(orbits.currentOrbitDetails).toBeNull()
    expect(localStorage.getItem('currentOrganizationId')).toBeNull()
    expect(localStorage.getItem('currentOrbitId')).toBeNull()
    expect(apiMocks.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('clears the departed orbit when the remaining organization has no orbits', async () => {
    const { store, orbits } = selectedOrganization()
    apiMocks.getOrganizationOrbits.mockResolvedValue([])

    await store.leaveOrganization(firstOrganization.id)

    expect(store.currentOrganization?.id).toBe(secondOrganization.id)
    expect(orbits.currentOrbitId).toBeNull()
    expect(localStorage.getItem('currentOrbitId')).toBeNull()
  })

  it('keeps the current selection when leaving a different organization', async () => {
    const { store, orbits } = selectedOrganization()

    await store.leaveOrganization(secondOrganization.id)

    expect(store.availableOrganizations).toEqual([firstOrganization])
    expect(store.currentOrganization?.id).toBe(firstOrganization.id)
    expect(store.organizationDetails?.id).toBe(firstOrganization.id)
    expect(orbits.currentOrbitId).toBe(firstOrbit.id)
    expect(LocalStorageService.get('currentOrganizationId')).toBe(firstOrganization.id)
    expect(LocalStorageService.get('currentOrbitId')).toBe(firstOrbit.id)
    expect(apiMocks.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('keeps membership and selection when leaving fails', async () => {
    const { store, orbits } = selectedOrganization()
    apiMocks.leaveOrganization.mockRejectedValue(new Error('unavailable'))

    await expect(store.leaveOrganization(firstOrganization.id)).rejects.toThrow('unavailable')

    expect(store.availableOrganizations).toEqual([firstOrganization, secondOrganization])
    expect(store.currentOrganization?.id).toBe(firstOrganization.id)
    expect(store.organizationDetails?.id).toBe(firstOrganization.id)
    expect(orbits.currentOrbitId).toBe(firstOrbit.id)
    expect(LocalStorageService.get('currentOrganizationId')).toBe(firstOrganization.id)
    expect(LocalStorageService.get('currentOrbitId')).toBe(firstOrbit.id)
  })

  it('does not retain departed organization data when loading the replacement fails', async () => {
    const { store, orbits } = selectedOrganization()
    apiMocks.getOrganizationOrbits.mockRejectedValue(new Error('unavailable'))

    await expect(store.leaveOrganization(firstOrganization.id)).rejects.toThrow('unavailable')

    expect(store.availableOrganizations).toEqual([secondOrganization])
    expect(store.currentOrganization?.id).toBe(secondOrganization.id)
    expect(store.organizationDetails).toBeNull()
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitId).toBeNull()
    expect(LocalStorageService.get('currentOrganizationId')).toBe(secondOrganization.id)
    expect(localStorage.getItem('currentOrbitId')).toBeNull()
  })
})
