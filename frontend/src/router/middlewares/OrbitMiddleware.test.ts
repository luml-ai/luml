import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { api } from '@/lib/api'
import type { Orbit, Organization } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useOrbitsStore } from '@/stores/orbits'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { orbitMiddleware } from './OrbitMiddleware'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuth: true }),
}))

vi.mock('@/lib/api', () => ({
  api: {
    getOrganizations: vi.fn(),
    getOrganizationOrbits: vi.fn(),
    getOrganization: vi.fn(),
    getOrbitDetails: vi.fn(),
  },
}))

const organizations = [
  { id: 'organization-a', name: 'Organization A' },
  { id: 'organization-b', name: 'Organization B' },
] as Organization[]
const savedOrbit = { id: 'orbit-a', organization_id: 'organization-a' } as Orbit
const firstOrbit = { id: 'orbit-b-first', organization_id: 'organization-b' } as Orbit
const urlOrbit = { id: 'orbit-b-url', organization_id: 'organization-b' } as Orbit
const from = {} as RouteLocationNormalized
const to = {
  name: 'track',
  params: { organizationId: 'organization-b', id: urlOrbit.id, trackId: 'track-b' },
} as unknown as RouteLocationNormalized

describe('orbitMiddleware URL selection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    LocalStorageService.set('currentOrganizationId', 'organization-a')
    LocalStorageService.set('currentOrbitId', savedOrbit.id)
    vi.mocked(api.getOrganizations).mockResolvedValue(organizations)
    vi.mocked(api.getOrganizationOrbits).mockImplementation(async (id) =>
      id === 'organization-a' ? [savedOrbit] : [firstOrbit, urlOrbit],
    )
  })

  it.each([{ savedOrbits: [] }, { savedOrbits: [savedOrbit] }])(
    'uses the URL organization and orbit when saved organization orbits are $savedOrbits',
    async ({ savedOrbits }) => {
      vi.mocked(api.getOrganizationOrbits).mockImplementation(async (id) =>
        id === 'organization-a' ? savedOrbits : [firstOrbit, urlOrbit],
      )
      const next = vi.fn() as NavigationGuardNext

      await orbitMiddleware(to, from, next)
      await flushPromises()

      expect(useOrganizationStore().currentOrganization).toEqual(organizations[1])
      expect(useOrbitsStore().orbitsList).toEqual([firstOrbit, urlOrbit])
      expect(useOrbitsStore().currentOrbit).toEqual(urlOrbit)
      expect(LocalStorageService.get('currentOrganizationId')).toBe('organization-b')
      expect(LocalStorageService.get('currentOrbitId')).toBe(urlOrbit.id)
      expect(next).toHaveBeenCalledWith()
    },
  )

  it('waits for background initialization even after the organization list is populated', async () => {
    let resolveSavedOrbits!: (value: Orbit[]) => void
    vi.mocked(api.getOrganizationOrbits).mockImplementation(async (id) => {
      if (id === 'organization-a') {
        return new Promise((resolve) => {
          resolveSavedOrbits = resolve
        })
      }
      return [firstOrbit, urlOrbit]
    })
    const store = useOrganizationStore()
    const background = store.getAvailableOrganizations()
    await flushPromises()
    expect(store.availableOrganizations).toEqual(organizations)
    const next = vi.fn() as NavigationGuardNext
    const navigation = orbitMiddleware(to, from, next)
    await flushPromises()
    expect(next).not.toHaveBeenCalled()

    resolveSavedOrbits([])
    await Promise.all([background, navigation])
    await flushPromises()

    expect(store.currentOrganization).toEqual(organizations[1])
    expect(useOrbitsStore().currentOrbit).toEqual(urlOrbit)
    expect(useOrbitsStore().orbitsList).toEqual([firstOrbit, urlOrbit])
    expect(next).toHaveBeenCalledWith()
  })

  it('replaces an already loaded orbit list from another organization', async () => {
    await useOrganizationStore().getAvailableOrganizations()
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(useOrganizationStore().currentOrganization).toEqual(organizations[1])
    expect(useOrbitsStore().currentOrbit).toEqual(urlOrbit)
    expect(useOrbitsStore().orbitsList).toEqual([firstOrbit, urlOrbit])
    expect(next).toHaveBeenCalledWith()
  })

  it('preserves URL selection when a background organization refresh finishes after navigation', async () => {
    const next = vi.fn() as NavigationGuardNext
    await orbitMiddleware(to, from, next)
    expect(next).toHaveBeenCalledWith()
    vi.mocked(api.getOrganizationOrbits).mockClear()
    let resolveOrganizations!: (value: Organization[]) => void
    vi.mocked(api.getOrganizations).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOrganizations = resolve
      }),
    )
    const refresh = useOrganizationStore().getAvailableOrganizations()

    resolveOrganizations(organizations)
    await refresh

    expect(useOrganizationStore().currentOrganization).toEqual(organizations[1])
    expect(useOrbitsStore().currentOrbit).toEqual(urlOrbit)
    expect(useOrbitsStore().orbitsList).toEqual([firstOrbit, urlOrbit])
    expect(api.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('redirects to setup when organizations fail to load', async () => {
    vi.mocked(api.getOrganizations).mockRejectedValueOnce(new Error('Organizations unavailable'))
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'registry' } })
    expect(api.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('redirects unavailable URL organizations to setup', async () => {
    vi.mocked(api.getOrganizations).mockResolvedValueOnce([organizations[0]])
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'registry' } })
    expect(api.getOrganizationOrbits).not.toHaveBeenCalledWith('organization-b')
  })

  it('redirects a missing URL orbit to an orbit from the URL organization', async () => {
    vi.mocked(api.getOrganizationOrbits).mockImplementation(async (id) =>
      id === 'organization-a' ? [savedOrbit] : [firstOrbit],
    )
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(next).toHaveBeenCalledWith({
      name: 'track',
      params: { organizationId: 'organization-b', id: firstOrbit.id },
    })
  })

  it('redirects to setup when the URL organization has no orbits', async () => {
    vi.mocked(api.getOrganizationOrbits).mockResolvedValue([])
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(useOrganizationStore().currentOrganization).toEqual(organizations[1])
    expect(useOrbitsStore().currentOrbit).toBeNull()
    expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'registry' } })
  })

  it('redirects to setup when the URL orbit list fails to load', async () => {
    vi.mocked(api.getOrganizationOrbits).mockImplementation(async (id) => {
      if (id === 'organization-b') throw new Error('Orbits unavailable')
      return [savedOrbit]
    })
    const next = vi.fn() as NavigationGuardNext

    await orbitMiddleware(to, from, next)

    expect(useOrbitsStore().currentOrbit).toBeNull()
    expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'registry' } })
  })
})
