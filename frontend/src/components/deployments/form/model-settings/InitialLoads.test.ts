import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import CollectionSelect from './CollectionSelect.vue'
import RegistryCollectionSelect from '@/components/orbits/tabs/registry/CollectionSelect.vue'
import ModelSelect from './ModelSelect.vue'

const mocks = vi.hoisted(() => ({
  getCollection: vi.fn(),
  getArtifact: vi.fn(),
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
    getInitialPage: vi.fn(),
    collectionsList: { value: [] },
    reset: vi.fn(),
    onLazyLoad: vi.fn(),
    addCollectionsToList: mocks.add,
  }),
}))
vi.mock('@/hooks/useArtifactsList', () => ({
  useArtifactsList: () => ({
    setRequestInfo: vi.fn(),
    getInitialPage: vi.fn(),
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

it.each([
  ['deployment collection', CollectionSelect],
  ['registry collection', RegistryCollectionSelect],
  ['model', ModelSelect],
] as const)('reports a rejected initial %s load', async (_, component) => {
  mocks.getCollection.mockRejectedValue(new Error('Collection unavailable'))
  mocks.getArtifact.mockRejectedValue(new Error('Model unavailable'))
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
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({
      severity: 'error',
      detail: component === ModelSelect ? 'Model unavailable' : 'Collection unavailable',
    }),
  )
  expect(mocks.add).not.toHaveBeenCalled()
})
