import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { createMemoryHistory, createRouter } from 'vue-router'
import { api } from '@/lib/api'
import type { Orbit, Organization } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useOrbitsStore } from '@/stores/orbits'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { orbitMiddleware } from './OrbitMiddleware'

const authStore = vi.hoisted(() => ({ isAuth: true }))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authStore,
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
      name: 'orbit-tracks',
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

describe('orbitMiddleware for a user who is not signed in', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    authStore.isAuth = false
  })

  afterEach(() => {
    authStore.isAuth = true
  })

  it('sends the user from the Flow page to the Flow tab of the setup page', async () => {
    const next = vi.fn() as NavigationGuardNext
    const flowRoute = { name: 'orbit-flow', params: {} } as unknown as RouteLocationNormalized

    await orbitMiddleware(flowRoute, from, next)

    expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'flow' } })
  })
})

describe('orbitMiddleware deep-link navigation', () => {
  const routes = [
    { name: 'orbit-collections', path: '' },
    { name: 'orbit-tracks', path: '/tracks' },
    { name: 'orbit-deployments', path: '/deployments' },
    { name: 'orbit-satellites', path: '/satellites' },
    { name: 'orbit-secrets', path: '/secrets' },
    { name: 'track', path: '/tracks/:trackId' },
    { name: 'collection', path: '/collection/:collectionId' },
    { name: 'artifact', path: '/collection/:collectionId/artifacts/:artifactId' },
    { name: 'dataset', path: '/collection/:collectionId/artifacts/:artifactId/data' },
    { name: 'deployment-schema', path: '/deployments/:deploymentId/schema' },
    { name: 'deployment-monitoring', path: '/deployments/:deploymentId/monitoring' },
  ]

  function createTestRouter() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { name: 'setup', path: '/setup', component: {} },
        ...routes.map(({ name, path }) => ({
          name,
          path: `/organization/:organizationId/orbit/:id${path}`,
          component: {},
        })),
      ],
    })
    router.beforeEach((to, from, next) => {
      if (to.name === 'setup') return next()
      return orbitMiddleware(to, from, next)
    })
    return router
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    useOrganizationStore().availableOrganizations = organizations
    useOrganizationStore().setCurrentOrganizationId('organization-b')
    useOrbitsStore().orbitsList = [firstOrbit, urlOrbit]
    vi.mocked(api.getOrganizationOrbits).mockResolvedValue([])
  })

  it.each([
    ['/collection/collection-missing', 'orbit-collections', ''],
    ['/collection/collection-missing/artifacts/artifact-missing', 'orbit-collections', ''],
    ['/collection/collection-missing/artifacts/artifact-missing/data', 'orbit-collections', ''],
    ['/tracks/track-missing', 'orbit-tracks', '/tracks'],
    ['/deployments/deployment-missing/schema', 'orbit-deployments', '/deployments'],
    ['/deployments/deployment-missing/monitoring', 'orbit-deployments', '/deployments'],
    ['', 'orbit-collections', ''],
    ['/tracks', 'orbit-tracks', '/tracks'],
    ['/deployments', 'orbit-deployments', '/deployments'],
    ['/satellites', 'orbit-satellites', '/satellites'],
    ['/secrets', 'orbit-secrets', '/secrets'],
  ])('redirects a missing orbit at %s to %s', async (path, name, tabPath) => {
    const router = createTestRouter()

    await router.push(`/organization/organization-b/orbit/missing${path}`)

    expect(router.currentRoute.value.name).toBe(name)
    expect(router.currentRoute.value.path).toBe(
      `/organization/organization-b/orbit/${firstOrbit.id}${tabPath}`,
    )
    expect(router.currentRoute.value.params).toEqual({
      organizationId: 'organization-b',
      id: firstOrbit.id,
    })
    expect(useOrbitsStore().currentOrbit).toEqual(firstOrbit)
  })

  it('preserves resource parameters when the URL orbit exists', async () => {
    const router = createTestRouter()
    const path = `/organization/organization-b/orbit/${urlOrbit.id}/collection/collection-b/artifacts/artifact-b`

    await router.push(path)

    expect(router.currentRoute.value.path).toBe(path)
    expect(router.currentRoute.value.name).toBe('artifact')
    expect(router.currentRoute.value.params).toEqual({
      organizationId: 'organization-b',
      id: urlOrbit.id,
      collectionId: 'collection-b',
      artifactId: 'artifact-b',
    })
    expect(useOrbitsStore().currentOrbit).toEqual(urlOrbit)
  })

  it.each([
    ['/collection/collection-missing/artifacts/artifact-missing', 'registry'],
    ['/tracks/track-missing', 'registry'],
    ['/deployments/deployment-missing/monitoring', 'deployments'],
    ['/deployments', 'deployments'],
    ['/satellites', 'satellites'],
  ])('redirects %s to setup when no orbit is available', async (path, tab) => {
    useOrbitsStore().orbitsList = []
    const router = createTestRouter()

    await router.push(`/organization/organization-b/orbit/missing${path}`)

    expect(router.currentRoute.value.name).toBe('setup')
    expect(router.currentRoute.value.query).toEqual({ tab })
  })
})
