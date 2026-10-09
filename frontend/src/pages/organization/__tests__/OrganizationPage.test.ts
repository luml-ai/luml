import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import type { Orbit, Organization } from '@/lib/api/api.interfaces'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import OrganizationPage from '../index.vue'

const harness = vi.hoisted(() => ({
  route: { name: 'organization', params: { id: 'organization-b' } },
  routerPush: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => harness.route,
    useRouter: () => ({ push: harness.routerPush }),
  }
})
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: harness.toastAdd }) }
})
vi.mock('@/lib/api', () => ({
  api: {
    getOrganizations: vi.fn(),
    getOrganizationOrbits: vi.fn(),
    getOrganization: vi.fn(),
    getOrbitDetails: vi.fn(),
  },
}))

const organizationA = { id: 'organization-a', name: 'A', role: 'owner' } as Organization
const organizationB = { id: 'organization-b', name: 'B', role: 'owner' } as Organization
const orbitsByOrganization: Record<string, Orbit[]> = {
  'organization-a': [{ id: 'orbit-a', name: 'Orbit A' } as Orbit],
  'organization-b': [{ id: 'orbit-b', name: 'Orbit B' } as Orbit],
}

function mountPage() {
  return shallowMount(OrganizationPage, {
    global: {
      stubs: {
        UiPageLoader: true,
        OrganizationLocked: true,
        OrganizationInfo: true,
        OrganizationLimits: true,
        OrganizationTabs: true,
        RouterView: true,
      },
    },
  })
}

describe('OrganizationPage', () => {
  let wrapper: ReturnType<typeof shallowMount> | null = null

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    vi.mocked(api.getOrganizationOrbits).mockImplementation(
      async (id: string) => orbitsByOrganization[id],
    )
    vi.mocked(api.getOrganization).mockImplementation(
      async (id: string) => ({ id, orbits: [] }) as never,
    )
    vi.mocked(api.getOrbitDetails).mockResolvedValue({} as never)
  })

  afterEach(() => wrapper?.unmount())

  it('loads the URL organization orbits when reloaded before the organization list resolves', async () => {
    LocalStorageService.set('currentOrganizationId', organizationA.id)
    let resolveOrganizations!: (value: Organization[]) => void
    vi.mocked(api.getOrganizations).mockReturnValue(
      new Promise((resolve) => {
        resolveOrganizations = resolve
      }),
    )
    const organizationStore = useOrganizationStore()
    const orbitsStore = useOrbitsStore()
    const organizationsLoaded = organizationStore.getAvailableOrganizations()

    wrapper = mountPage()
    await flushPromises()
    resolveOrganizations([organizationA, organizationB])
    await organizationsLoaded
    await flushPromises()

    expect(organizationStore.currentOrganization?.id).toBe(organizationB.id)
    expect(orbitsStore.orbitsList).toEqual(orbitsByOrganization[organizationB.id])
    expect(orbitsStore.currentOrbitId).toBe('orbit-b')
    expect(api.getOrganizationOrbits).not.toHaveBeenCalledWith(organizationA.id)
    expect(harness.routerPush).not.toHaveBeenCalled()
  })

  it('replaces the previous organization orbits when opening another organization', async () => {
    vi.mocked(api.getOrganizations).mockResolvedValue([organizationA, organizationB])
    const organizationStore = useOrganizationStore()
    const orbitsStore = useOrbitsStore()
    await organizationStore.getAvailableOrganizations()
    expect(orbitsStore.currentOrbitId).toBe('orbit-a')

    wrapper = mountPage()
    await flushPromises()

    expect(organizationStore.currentOrganization?.id).toBe(organizationB.id)
    expect(orbitsStore.orbitsList).toEqual(orbitsByOrganization[organizationB.id])
    expect(orbitsStore.currentOrbitId).toBe('orbit-b')
    expect(harness.routerPush).not.toHaveBeenCalled()
  })

  it('switches after an in-flight organization refresh instead of racing it', async () => {
    vi.mocked(api.getOrganizations).mockResolvedValueOnce([organizationA, organizationB])
    const organizationStore = useOrganizationStore()
    const orbitsStore = useOrbitsStore()
    await organizationStore.getAvailableOrganizations()
    let resolveRefresh!: (value: Organization[]) => void
    vi.mocked(api.getOrganizations).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRefresh = resolve
      }),
    )
    const refresh = organizationStore.getAvailableOrganizations()

    wrapper = mountPage()
    await flushPromises()
    expect(organizationStore.currentOrganization?.id).toBe(organizationA.id)

    resolveRefresh([organizationA, organizationB])
    await refresh
    await flushPromises()

    expect(organizationStore.currentOrganization?.id).toBe(organizationB.id)
    expect(orbitsStore.orbitsList).toEqual(orbitsByOrganization[organizationB.id])
  })

  it('only reloads details when the URL organization is already current', async () => {
    harness.route.params.id = organizationA.id
    vi.mocked(api.getOrganizations).mockResolvedValue([organizationA, organizationB])
    const organizationStore = useOrganizationStore()
    await organizationStore.getAvailableOrganizations()
    vi.mocked(api.getOrganizationOrbits).mockClear()

    wrapper = mountPage()
    await flushPromises()

    expect(api.getOrganizationOrbits).not.toHaveBeenCalled()
    expect(api.getOrganization).toHaveBeenLastCalledWith(organizationA.id)
    harness.route.params.id = organizationB.id
  })
})
