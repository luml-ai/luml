import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  Orbit,
  OrbitDetails,
  Organization,
  OrganizationDetails,
} from '@/lib/api/api.interfaces'
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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('organization switching', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    apiMocks.getOrganization.mockImplementation(async (id: string) => ({ id }))
    apiMocks.getOrganizationOrbits.mockResolvedValue([])
    apiMocks.getOrbitDetails.mockResolvedValue({})
  })

  function setup() {
    const store = useOrganizationStore()
    store.availableOrganizations = [firstOrganization, secondOrganization]
    return { store, orbits: useOrbitsStore() }
  }

  it('keeps the latest organization when older orbits arrive last', async () => {
    const { store, orbits } = setup()
    const oldOrbits = deferred<Orbit[]>()
    apiMocks.getOrganizationOrbits.mockReturnValueOnce(oldOrbits.promise)
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([secondOrbit])

    const first = store.switchOrganization(firstOrganization.id)
    await store.switchOrganization(secondOrganization.id)
    oldOrbits.resolve([firstOrbit])
    await first

    expect(store.currentOrganization).toEqual(secondOrganization)
    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(orbits.orbitsList).toEqual([secondOrbit])
    expect(orbits.currentOrbitId).toBe(secondOrbit.id)
    expect(LocalStorageService.get('currentOrganizationId')).toBe(secondOrganization.id)
    expect(LocalStorageService.get('currentOrbitId')).toBe(secondOrbit.id)
    expect(apiMocks.getOrganization).not.toHaveBeenCalledWith(firstOrganization.id)
  })

  it('discards an older detail response and preserves the latest loading state', async () => {
    const { store } = setup()
    const oldDetails = deferred<OrganizationDetails>()
    const newDetails = deferred<OrganizationDetails>()
    apiMocks.getOrganization.mockReturnValueOnce(oldDetails.promise)
    apiMocks.getOrganization.mockReturnValueOnce(newDetails.promise)
    const first = store.switchOrganization(firstOrganization.id)
    await vi.waitFor(() => expect(apiMocks.getOrganization).toHaveBeenCalledOnce())
    const second = store.switchOrganization(secondOrganization.id)
    await vi.waitFor(() => expect(apiMocks.getOrganization).toHaveBeenCalledTimes(2))

    oldDetails.resolve({ id: firstOrganization.id } as OrganizationDetails)
    await first
    expect(store.organizationDetails).toBeNull()
    expect(store.loading).toBe(true)

    newDetails.resolve({ id: secondOrganization.id } as OrganizationDetails)
    await second
    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(store.loading).toBe(false)
  })

  it('invalidates older requests even when switching back to the same organization', async () => {
    const { store, orbits } = setup()
    const oldOrbits = deferred<Orbit[]>()
    apiMocks.getOrganizationOrbits.mockReturnValueOnce(oldOrbits.promise)
    const first = store.switchOrganization(firstOrganization.id)
    await store.switchOrganization(secondOrganization.id)
    await store.switchOrganization(firstOrganization.id)
    oldOrbits.resolve([firstOrbit])
    await first

    expect(store.currentOrganization).toEqual(firstOrganization)
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitId).toBeNull()
  })

  it('discards old orbit details after switching away and back to the same orbit', async () => {
    const { store, orbits } = setup()
    const oldDetails = deferred<OrbitDetails>()
    apiMocks.getOrganizationOrbits.mockResolvedValue([firstOrbit])
    apiMocks.getOrbitDetails.mockReturnValueOnce(oldDetails.promise)
    await store.switchOrganization(firstOrganization.id)
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([])
    await store.switchOrganization(secondOrganization.id)
    apiMocks.getOrbitDetails.mockResolvedValueOnce({ id: firstOrbit.id, name: 'New' })
    await store.switchOrganization(firstOrganization.id)

    oldDetails.resolve({ id: firstOrbit.id, name: 'Old' } as OrbitDetails)
    await oldDetails.promise
    await Promise.resolve()

    expect(orbits.currentOrbitDetails?.name).toBe('New')
    expect(orbits.isLoadingOrbitDetails).toBe(false)
  })

  it('does not let a superseded switch finish a newer detail refresh', async () => {
    const { store } = setup()
    const oldDetails = deferred<OrganizationDetails>()
    const newDetails = deferred<OrganizationDetails>()
    apiMocks.getOrganization.mockReturnValueOnce(oldDetails.promise)
    apiMocks.getOrganization.mockReturnValueOnce(newDetails.promise)
    const switching = store.switchOrganization(firstOrganization.id)
    await vi.waitFor(() => expect(apiMocks.getOrganization).toHaveBeenCalledOnce())
    const refresh = store.getOrganizationDetails(firstOrganization.id)

    oldDetails.resolve({ id: firstOrganization.id, name: 'Old' } as OrganizationDetails)
    await switching
    expect(store.loading).toBe(true)
    expect(store.organizationDetails).toBeNull()
    newDetails.resolve({ id: firstOrganization.id, name: 'New' } as OrganizationDetails)
    await refresh
    expect(store.organizationDetails?.name).toBe('New')
    expect(store.loading).toBe(false)
  })

  it('ignores a superseded orbit request failure', async () => {
    const { store, orbits } = setup()
    const oldOrbits = deferred<Orbit[]>()
    apiMocks.getOrganizationOrbits.mockReturnValueOnce(oldOrbits.promise)
    const first = store.switchOrganization(firstOrganization.id)
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([secondOrbit])
    await store.switchOrganization(secondOrganization.id)
    oldOrbits.reject(new Error('unavailable'))
    await expect(first).resolves.toBeUndefined()

    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(orbits.orbitsList).toEqual([secondOrbit])
  })

  it('clears previous details immediately and keeps them cleared if new orbits fail', async () => {
    const { store, orbits } = setup()
    await store.switchOrganization(firstOrganization.id)
    apiMocks.getOrganizationOrbits.mockRejectedValueOnce(new Error('unavailable'))

    const switching = store.switchOrganization(secondOrganization.id)
    expect(store.organizationDetails).toBeNull()
    await expect(switching).rejects.toThrow('unavailable')
    expect(orbits.orbitsList).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('discards detail refreshes after switching organizations', async () => {
    const { store } = setup()
    await store.switchOrganization(firstOrganization.id)
    const oldDetails = deferred<OrganizationDetails>()
    apiMocks.getOrganization.mockReturnValueOnce(oldDetails.promise)
    const refresh = store.getOrganizationDetails(firstOrganization.id)
    await store.switchOrganization(secondOrganization.id)
    oldDetails.resolve({ id: firstOrganization.id } as OrganizationDetails)
    await refresh

    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(store.loading).toBe(false)
  })

  it('does not repopulate organization or orbit state after a reset', async () => {
    const { store, orbits } = setup()
    const pendingOrbits = deferred<Orbit[]>()
    apiMocks.getOrganizationOrbits.mockReturnValueOnce(pendingOrbits.promise)
    const switching = store.switchOrganization(firstOrganization.id)
    store.resetCurrentOrganization()
    pendingOrbits.resolve([firstOrbit])
    await switching

    expect(store.currentOrganization).toBeNull()
    expect(store.organizationDetails).toBeNull()
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitId).toBeNull()
    expect(LocalStorageService.get('currentOrganizationId')).toBeNull()
    expect(LocalStorageService.get('currentOrbitId')).toBeNull()
    expect(apiMocks.getOrganization).not.toHaveBeenCalled()
  })

  it('invalidates pending organization and orbit details when resetting', async () => {
    const { store, orbits } = setup()
    const pendingDetails = deferred<OrganizationDetails>()
    const pendingOrbitDetails = deferred<typeof orbits.currentOrbitDetails>()
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([firstOrbit])
    apiMocks.getOrganization.mockReturnValueOnce(pendingDetails.promise)
    apiMocks.getOrbitDetails.mockReturnValueOnce(pendingOrbitDetails.promise)
    const switching = store.switchOrganization(firstOrganization.id)
    await vi.waitFor(() => expect(apiMocks.getOrganization).toHaveBeenCalledOnce())

    store.resetCurrentOrganization()
    pendingDetails.resolve({ id: firstOrganization.id } as OrganizationDetails)
    pendingOrbitDetails.resolve({ id: firstOrbit.id } as typeof orbits.currentOrbitDetails)
    await switching

    expect(store.currentOrganization).toBeNull()
    expect(store.organizationDetails).toBeNull()
    expect(store.loading).toBe(false)
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitDetails).toBeNull()
    expect(orbits.isLoadingOrbitDetails).toBe(false)
  })

  it('waits for the replacement organization when deleting the current organization', async () => {
    const { store, orbits } = setup()
    await store.switchOrganization(firstOrganization.id)
    const pendingOrbits = deferred<Orbit[]>()
    const pendingDetails = deferred<OrganizationDetails>()
    apiMocks.getOrganizationOrbits.mockReturnValueOnce(pendingOrbits.promise)
    apiMocks.getOrganization.mockReturnValueOnce(pendingDetails.promise)
    const settled = vi.fn()
    const deletion = store.deleteOrganization(firstOrganization.id).then(settled)
    await vi.waitFor(() => expect(store.currentOrganization).toEqual(secondOrganization))
    expect(settled).not.toHaveBeenCalled()

    pendingOrbits.resolve([secondOrbit])
    await vi.waitFor(() =>
      expect(apiMocks.getOrganization).toHaveBeenLastCalledWith(secondOrganization.id),
    )
    expect(settled).not.toHaveBeenCalled()
    pendingDetails.resolve({ id: secondOrganization.id } as OrganizationDetails)
    await deletion

    expect(settled).toHaveBeenCalledOnce()
    expect(store.organizationDetails?.id).toBe(secondOrganization.id)
    expect(orbits.orbitsList).toEqual([secondOrbit])
  })

  it('clears all selection state when deleting the last organization', async () => {
    const { store, orbits } = setup()
    store.availableOrganizations = [firstOrganization]
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([firstOrbit])
    await store.switchOrganization(firstOrganization.id)

    await store.deleteOrganization(firstOrganization.id)

    expect(store.currentOrganization).toBeNull()
    expect(store.organizationDetails).toBeNull()
    expect(orbits.orbitsList).toEqual([])
    expect(orbits.currentOrbitId).toBeNull()
    expect(orbits.currentOrbitDetails).toBeNull()
    expect(LocalStorageService.get('currentOrganizationId')).toBeNull()
    expect(LocalStorageService.get('currentOrbitId')).toBeNull()
  })

  it('preserves the selection when deleting another organization or deletion fails', async () => {
    const { store, orbits } = setup()
    apiMocks.getOrganizationOrbits.mockResolvedValueOnce([firstOrbit])
    await store.switchOrganization(firstOrganization.id)
    apiMocks.deleteOrganization.mockRejectedValueOnce(new Error('unavailable'))

    await expect(store.deleteOrganization(firstOrganization.id)).rejects.toThrow('unavailable')
    expect(store.availableOrganizations).toEqual([firstOrganization, secondOrganization])
    await store.deleteOrganization(secondOrganization.id)

    expect(store.currentOrganization).toEqual(firstOrganization)
    expect(store.organizationDetails?.id).toBe(firstOrganization.id)
    expect(orbits.orbitsList).toEqual([firstOrbit])
    expect(LocalStorageService.get('currentOrganizationId')).toBe(firstOrganization.id)
    expect(LocalStorageService.get('currentOrbitId')).toBe(firstOrbit.id)
  })
})
