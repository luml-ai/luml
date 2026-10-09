import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Orbit, Organization, OrganizationDetails } from '@/lib/api/api.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { useOrganizationStore } from '../organization'
import { useOrbitsStore } from '../orbits'

const apiMocks = vi.hoisted(() => ({
  getOrganizations: vi.fn(),
  createOrganization: vi.fn(),
  deleteOrganization: vi.fn(),
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

const organizations = [{ id: 'organization-a', name: 'Organization A' }] as Organization[]

describe('organization initialization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    apiMocks.getOrganizationOrbits.mockResolvedValue([])
  })

  it('waits for initialization and settles all concurrent callers', async () => {
    let resolveOrganizations!: (value: Organization[]) => void
    apiMocks.getOrganizations.mockReturnValue(
      new Promise((resolve) => {
        resolveOrganizations = resolve
      }),
    )
    const store = useOrganizationStore()
    const settled = vi.fn()
    const first = store.getAvailableOrganizations().then(settled)
    const second = store.getAvailableOrganizations().then(settled)
    await Promise.resolve()
    expect(settled).not.toHaveBeenCalled()
    expect(apiMocks.getOrganizations).toHaveBeenCalledOnce()

    resolveOrganizations(organizations)
    await Promise.all([first, second])

    expect(settled).toHaveBeenCalledTimes(2)
    expect(store.currentOrganization?.id).toBe('organization-a')
    expect(apiMocks.getOrganizationOrbits).toHaveBeenCalledWith('organization-a')
  })

  it('rejects concurrent callers on failure and permits a retry', async () => {
    const error = new Error('Organizations unavailable')
    apiMocks.getOrganizations.mockRejectedValueOnce(error)
    const store = useOrganizationStore()
    const first = store.getAvailableOrganizations()
    const second = store.getAvailableOrganizations()

    await expect(first).rejects.toThrow(error)
    await expect(second).rejects.toThrow(error)
    expect(store.availableOrganizations).toEqual([])

    apiMocks.getOrganizations.mockResolvedValueOnce(organizations)
    await store.getAvailableOrganizations()
    expect(store.currentOrganization?.id).toBe('organization-a')
  })

  it('retains the saved organization fallback when there is no URL organization', async () => {
    const saved = { id: 'organization-b', name: 'Organization B' } as Organization
    LocalStorageService.set('currentOrganizationId', saved.id)
    apiMocks.getOrganizations.mockResolvedValueOnce([...organizations, saved])
    const store = useOrganizationStore()

    await store.getAvailableOrganizations()

    expect(store.currentOrganization).toEqual(saved)
  })

  it('settles when the user has no organizations', async () => {
    apiMocks.getOrganizations.mockResolvedValueOnce([])
    const store = useOrganizationStore()

    await store.getAvailableOrganizations()

    expect(store.currentOrganization).toBeNull()
    expect(apiMocks.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('keeps the current organization when creating another organization', async () => {
    const store = useOrganizationStore()
    store.availableOrganizations = organizations
    store.setCurrentOrganizationId(organizations[0].id)
    apiMocks.getOrganizations.mockResolvedValueOnce([
      ...organizations,
      { id: 'organization-b', name: 'Organization B' } as Organization,
    ])

    await store.createOrganization({ name: 'Organization B', logo: '' })

    expect(store.currentOrganization?.id).toBe('organization-a')
    expect(apiMocks.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('selects a remaining organization when the current organization is deleted', async () => {
    const store = useOrganizationStore()
    const remaining = { id: 'organization-b', name: 'Organization B' } as Organization
    store.availableOrganizations = [...organizations, remaining]
    store.setCurrentOrganizationId(organizations[0].id)

    await store.deleteOrganization(organizations[0].id)

    expect(store.currentOrganization).toEqual(remaining)
    expect(apiMocks.getOrganizationOrbits).toHaveBeenCalledWith(remaining.id)
    expect(LocalStorageService.get('currentOrganizationId')).toBe(remaining.id)
  })
})
