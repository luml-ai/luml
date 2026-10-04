import { enableAutoUnmount, flushPromises, mount, shallowMount } from '@vue/test-utils'
import { nextTick, reactive, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import RegistryHeader from '@/components/registry/RegistryHeader.vue'
import TracksCreator from '@/components/tracks/TracksCreator.vue'
import TracksView from '../TracksView.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  showTrackCreator: vi.fn(),
  showCollectionCreator: vi.fn(),
}))

const orbitStore = reactive({
  getCurrentOrbitPermissions: undefined as { track: PermissionEnum[] } | undefined,
})
const authStore = reactive({ isAuth: true })
const route = reactive({
  name: 'orbit-tracks',
  params: { organizationId: 'organization', id: 'orbit' },
})

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => orbitStore }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authStore }))
vi.mock('@/stores/tracks', () => ({
  useTracksStore: () => ({ showCreator: mocks.showTrackCreator }),
}))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ showCreator: mocks.showCollectionCreator }),
}))
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})
vi.mock('@/hooks/useTracksList', () => ({
  useTracksList: () => ({
    setRequestInfo: vi.fn(),
    getInitialPage: vi.fn().mockResolvedValue(undefined),
    tracksList: ref([]),
    reset: vi.fn(),
    searchQuery: ref(''),
    setSearchQuery: vi.fn(),
    onLazyLoad: vi.fn(),
    typesQuery: ref([]),
    setTypesQuery: vi.fn(),
    isLoading: ref(false),
  }),
}))

function mountHeader() {
  return mount(RegistryHeader, {
    global: {
      components: {
        'd-button': { props: ['label'], template: '<button>{{ label }}</button>' },
      },
    },
  })
}

describe('track creation permissions', () => {
  beforeEach(() => {
    route.name = 'orbit-tracks'
    authStore.isAuth = true
    orbitStore.getCurrentOrbitPermissions = undefined
  })

  it.each([
    ['permissions are loading', undefined],
    ['no track permissions', []],
    ['viewer permissions', [PermissionEnum.read]],
    [
      'other track permissions',
      [PermissionEnum.read, PermissionEnum.update, PermissionEnum.delete],
    ],
  ])('hides the button and creator with %s', async (_, track) => {
    orbitStore.getCurrentOrbitPermissions = track ? { track } : undefined
    const header = mountHeader()
    const view = shallowMount(TracksView)
    await flushPromises()

    expect(header.find('button').exists()).toBe(false)
    expect(view.findComponent(TracksCreator).exists()).toBe(false)
    expect(mocks.showTrackCreator).not.toHaveBeenCalled()
  })

  it('allows users with track:create to open the creator', async () => {
    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.create] }
    const header = mountHeader()
    const view = shallowMount(TracksView)
    await flushPromises()

    expect(header.get('button').text()).toBe('Create track')
    await header.get('button').trigger('click')
    expect(mocks.showTrackCreator).toHaveBeenCalledOnce()
    expect(view.findComponent(TracksCreator).exists()).toBe(true)
  })

  it('updates the button as orbit permissions load or change', async () => {
    const header = mountHeader()
    expect(header.find('button').exists()).toBe(false)

    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.create] }
    await nextTick()
    expect(header.find('button').exists()).toBe(true)

    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.read] }
    await nextTick()
    expect(header.find('button').exists()).toBe(false)
  })

  it('updates the creator as orbit permissions load or change', async () => {
    const view = shallowMount(TracksView)
    await flushPromises()
    expect(view.findComponent(TracksCreator).exists()).toBe(false)

    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.create] }
    await nextTick()
    expect(view.findComponent(TracksCreator).exists()).toBe(true)

    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.read] }
    await nextTick()
    expect(view.findComponent(TracksCreator).exists()).toBe(false)
  })

  it('keeps the create button hidden when unauthenticated', () => {
    authStore.isAuth = false
    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.create] }

    expect(mountHeader().find('button').exists()).toBe(false)
  })

  it('preserves collection creation on the collections tab', async () => {
    route.name = 'orbit-collections'
    orbitStore.getCurrentOrbitPermissions = { track: [PermissionEnum.read] }
    const header = mountHeader()

    expect(header.get('button').text()).toBe('Create collection')
    await header.get('button').trigger('click')
    expect(mocks.showCollectionCreator).toHaveBeenCalledOnce()
    expect(mocks.showTrackCreator).not.toHaveBeenCalled()
  })
})
