import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import CollectionSelect from './CollectionSelect.vue'
import RegistryCollectionSelect from '@/components/orbits/tabs/registry/CollectionSelect.vue'
import ModelSelect from './ModelSelect.vue'

const mocks = vi.hoisted(() => ({
  getCollection: vi.fn(),
  getArtifact: vi.fn(),
  getInitialPage: vi.fn(),
  toast: vi.fn(),
  add: vi.fn(),
}))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ getCollection: mocks.getCollection }),
}))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ getArtifact: mocks.getArtifact }),
}))
vi.mock('@/hooks/useCollectionsList', () => ({
  useCollectionsList: () => ({
    setRequestInfo: vi.fn(),
    getInitialPage: mocks.getInitialPage,
    collectionsList: { value: [] },
    reset: vi.fn(),
    onLazyLoad: vi.fn(),
    addCollectionsToList: mocks.add,
  }),
}))
vi.mock('@/hooks/useArtifactsList', () => ({
  useArtifactsList: () => ({
    setRequestInfo: vi.fn(),
    getInitialPage: mocks.getInitialPage,
    list: { value: [] },
    reset: vi.fn(),
    onLazyLoad: vi.fn(),
    addItemsToList: mocks.add,
  }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))
enableAutoUnmount(afterEach)
beforeEach(() => vi.resetAllMocks())

const selects = [
  ['deployment collection', CollectionSelect, 'Failed to load the selected collection'],
  ['registry collection', RegistryCollectionSelect, 'Failed to load the selected collection'],
  ['model', ModelSelect, 'Failed to load the selected model'],
] as const

function mountSelect(component: (typeof selects)[number][1]) {
  shallowMount(component as typeof CollectionSelect, {
    props: {
      disabled: false,
      organizationId: 'org',
      orbitId: 'orbit',
      collectionId: 'collection',
      initialCollectionId: 'collection',
      initialModelId: 'model',
    },
  })
}

it.each(selects)(
  'reports a rejected initial %s load and still loads the list',
  async (_, component) => {
    mocks.getCollection.mockRejectedValue(new Error('Collection unavailable'))
    mocks.getArtifact.mockRejectedValue(new Error('Model unavailable'))
    mountSelect(component)
    await flushPromises()
    expect(mocks.toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        severity: 'error',
        detail: component === ModelSelect ? 'Model unavailable' : 'Collection unavailable',
      }),
    )
    expect(mocks.add).not.toHaveBeenCalled()
    expect(mocks.getInitialPage).toHaveBeenCalledOnce()
  },
)

it.each(selects)(
  'names the selected %s when its rejection has no message',
  async (_, component, detail) => {
    mocks.getCollection.mockRejectedValue({ response: { status: 500 } })
    mocks.getArtifact.mockRejectedValue({ response: { status: 500 } })
    mountSelect(component)
    await flushPromises()
    expect(mocks.toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail }),
    )
    expect(mocks.getInitialPage).toHaveBeenCalledOnce()
  },
)

it.each(selects)(
  'reports both failures when the %s list also fails',
  async (_, component, detail) => {
    mocks.getCollection.mockRejectedValue({ response: { status: 500 } })
    mocks.getArtifact.mockRejectedValue({ response: { status: 500 } })
    mocks.getInitialPage.mockRejectedValue(new Error('List unavailable'))
    mountSelect(component)
    await flushPromises()
    expect(mocks.toast).toHaveBeenCalledTimes(2)
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ detail }))
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'List unavailable' }),
    )
  },
)
