import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  OrbitCollectionTypeEnum,
  type OrbitCollection,
} from '@/lib/api/orbit-collections/interfaces'
import CollectionEditor from './CollectionEditor.vue'

const mocks = vi.hoisted(() => ({
  updateCollection: vi.fn(),
  deleteCollection: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({
    collectionsList: [],
    updateCollection: mocks.updateCollection,
    deleteCollection: mocks.deleteCollection,
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ getCurrentOrbitPermissions: undefined }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return {
    ...actual,
    useToast: () => ({ add: mocks.toastAdd }),
    useConfirm: () => ({ require: vi.fn() }),
  }
})

const collection: OrbitCollection = {
  id: 'collection-1',
  orbit_id: 'orbit-1',
  name: 'Models',
  description: 'a'.repeat(1500),
  type: OrbitCollectionTypeEnum.model,
  tags: [],
  total_artifacts: 0,
  created_at: new Date(),
  updated_at: new Date(),
}

function mountEditor() {
  return mount(CollectionEditor, {
    props: { data: collection, visible: true },
    global: {
      stubs: {
        UiDialogRight: { template: '<div><slot /></div>' },
        Form: {
          template: '<form @submit.prevent="$emit(\'submit\', { valid: true })"><slot /></form>',
        },
        InputText: true,
        Textarea: true,
        AutoComplete: true,
      },
    },
  })
}

describe('CollectionEditor', () => {
  beforeEach(() => {
    mocks.updateCollection.mockRejectedValue({
      message: 'Request failed with status code 422',
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: 'string_too_long',
              loc: ['body', 'description'],
              msg: 'String should have at most 1000 characters',
              input: 'a'.repeat(1500),
              ctx: { max_length: 1000 },
            },
          ],
        },
      },
    })
  })

  it('shows the validation reason when an update fails', async () => {
    const wrapper = mountEditor()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.updateCollection).toHaveBeenCalledWith('collection-1', {
      name: 'Models',
      description: 'a'.repeat(1500),
      tags: [],
    })
    expect(mocks.toastAdd).toHaveBeenCalledWith({
      severity: 'error',
      summary: 'Error',
      detail: 'description: String should have at most 1000 characters',
      life: 3000,
    })
  })
})
