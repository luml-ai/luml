import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CollectionSelect from './CollectionSelect.vue'

const collectionsList = vi.hoisted(() => ({ value: [] as unknown[] }))

vi.mock('@/hooks/useCollectionsList', () => ({
  useCollectionsList: () => ({
    setRequestInfo: vi.fn(),
    getInitialPage: vi.fn(),
    collectionsList,
    reset: vi.fn(),
    onLazyLoad: vi.fn(),
    addCollectionsToList: vi.fn(),
  }),
}))

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ getCollection: vi.fn() }),
}))

vi.mock('primevue', () => ({
  Select: defineComponent({
    name: 'PrimeSelectStub',
    props: ['virtualScrollerOptions'],
    template: '<div />',
  }),
  useToast: () => ({ add: vi.fn() }),
}))

function mountSelect() {
  return shallowMount(CollectionSelect, {
    props: {
      disabled: false,
      organizationId: 'org-1',
      orbitId: 'orbit-1',
    },
  })
}

describe('CollectionSelect', () => {
  beforeEach(() => {
    collectionsList.value = []
  })

  it('allocates the full collection card height when options are virtualized', () => {
    collectionsList.value = Array.from({ length: 10 }, (_, index) => ({
      id: `collection-${index}`,
    }))

    const select = mountSelect().findComponent({ name: 'PrimeSelectStub' })

    expect(select.props('virtualScrollerOptions')).toMatchObject({ itemSize: 107 })
  })
})
