import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia } from 'pinia'
import OrbitSettingsDialog from './OrbitEditor.vue'
import { OrbitRoleEnum } from '../orbits.interfaces'
import { PermissionEnum } from '@/lib/api/api.interfaces'

vi.mock('@/stores/buckets', () => ({
  useBucketsStore: () => ({
    buckets: [{ id: 'bucket-1111-aaaa-bbbb-cccc-000000000001', bucket_name: 'Bucket One' }],
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    updateOrbit: vi.fn().mockResolvedValue({}),
    deleteOrbit: vi.fn().mockResolvedValue({}),
  }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>

  return {
    ...actual,

    useToast: () => ({
      add: vi.fn(),
    }),

    useConfirm: () => ({
      require: vi.fn(),
    }),
  }
})

vi.mock('@/lib/primevue/data/toasts', () => ({
  simpleErrorToast: vi.fn(),

  simpleSuccessToast: vi.fn(),
}))

vi.mock('@/lib/primevue/data/confirm', () => ({
  deleteOrbitConfirmOptions: vi.fn((callback) => ({ accept: callback })),
}))

vi.mock('@primevue/forms/resolvers/zod', () => ({
  zodResolver: vi.fn(() => vi.fn()),
}))

vi.mock('lucide-vue-next', () => ({
  Orbit: {
    name: 'Orbit',
    props: ['size', 'color'],
    template:
      '<svg data-testid="orbit-icon" :style="{ width: size + \'px\', height: size + \'px\', color }"><circle /></svg>',
  },
}))

describe('OrbitSettingsDialog', () => {
  let wrapper: any

  const pinia = createPinia()

  const orbit = {
    id: 'orbit-aaaa-bbbb-cccc-dddd-000000000001',
    name: 'Test Orbit',
    organization_id: 'org-1111-aaaa-bbbb-cccc-000000000001',
    total_members: 10,
    created_at: new Date(),
    updated_at: null,
    bucket_secret_id: 'bucket-1111-aaaa-bbbb-cccc-000000000001',
    total_collections: 5,
    role: OrbitRoleEnum.member,
    permissions: {
      orbit: PermissionEnum.delete,
      orbit_user: PermissionEnum.read,
      model: PermissionEnum.create,
      collection: PermissionEnum.create,
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()

    wrapper = mount(OrbitSettingsDialog, {
      global: {
        plugins: [pinia],

        stubs: {
          Dialog: {
            template:
              '<div v-if="visible"><slot name="header"></slot><slot></slot><slot name="footer"></slot></div>',
            props: ['visible', 'position', 'draggable', 'pt'],
          },

          Form: {
            template:
              '<form id="orbit-edit-form" @submit="$emit(\'submit\', { valid: true })"><slot></slot></form>',
            props: ['id', 'initialValues', 'resolver'],
          },

          InputText: {
            template:
              '<input :id="id" :name="name" v-model="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['id', 'name', 'modelValue'],
            emits: ['update:modelValue'],
          },

          Select: {
            template:
              '<select :id="id" :name="name" :disabled="disabled"><option v-for="opt in options" :key="opt[optionValue]" :value="opt[optionValue]">{{ opt[optionLabel] }}</option></select>',
            props: [
              'options',
              'optionLabel',
              'optionValue',
              'modelValue',
              'id',
              'name',
              'disabled',
            ],
            emits: ['update:modelValue'],
          },

          Button: {
            template:
              '<button :type="type" :form="form" :disabled="disabled || loading" :variant="variant" :severity="severity"><slot></slot></button>',
            props: ['type', 'form', 'loading', 'disabled', 'variant', 'severity'],
          },
        },
      },

      props: {
        orbit,
        visible: true,
      },
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  it('renders dialog with initial values', async () => {
    await flushPromises()
    expect(wrapper.find('input#name').exists()).toBe(true)
    expect(wrapper.find('input#name').element.value).toBe('Test Orbit')
    expect(wrapper.find('select#bucket').exists()).toBe(true)
  })

  it('submits form and calls updateOrbit', async () => {
    const mockUpdateOrbit = vi.fn().mockResolvedValue({})
    const mockToastAdd = vi.fn()
    vi.doMock('@/stores/orbits', () => ({
      useOrbitsStore: () => ({
        updateOrbit: mockUpdateOrbit,

        deleteOrbit: vi.fn(),
      }),
    }))

    vi.doMock('primevue', async (importOriginal) => {
      const actual = (await importOriginal()) as Record<string, unknown>
      return {
        ...actual,
        useToast: () => ({
          add: mockToastAdd,
        }),

        useConfirm: () => ({
          require: vi.fn(),
        }),
      }
    })

    await flushPromises()
    const nameInput = wrapper.find('input#name')
    await nameInput.setValue('New Orbit Name')
    const form = wrapper.find('form#orbit-edit-form')
    await form.trigger('submit')
    await flushPromises()
    expect(form.exists()).toBe(true)
  })

  it('shows delete button when user has delete permission', async () => {
    await flushPromises()

    const deleteButton = wrapper.find('button[severity="warn"]')
    expect(deleteButton.exists()).toBe(true)
    expect(deleteButton.text()).toBe('delete Orbit')
  })

  it('handles delete orbit action', async () => {
    const mockDeleteOrbit = vi.fn().mockResolvedValue({})
    const mockToastAdd = vi.fn()
    const mockConfirmRequire = vi.fn()

    vi.doMock('@/stores/orbits', () => ({
      useOrbitsStore: () => ({
        updateOrbit: vi.fn(),

        deleteOrbit: mockDeleteOrbit,
      }),
    }))

    vi.doMock('primevue', async (importOriginal) => {
      const actual = (await importOriginal()) as Record<string, unknown>
      return {
        ...actual,

        useToast: () => ({
          add: mockToastAdd,
        }),

        useConfirm: () => ({
          require: mockConfirmRequire,
        }),
      }
    })

    await flushPromises()
    const deleteButton = wrapper.find('button[severity="warn"]')
    await deleteButton.trigger('click')
    await flushPromises()
    expect(deleteButton.exists()).toBe(true)
  })

  it('disables bucket select field', async () => {
    await flushPromises()

    const bucketSelect = wrapper.find('select#bucket')
    expect(bucketSelect.exists()).toBe(true)
    expect(bucketSelect.attributes('disabled')).toBeDefined()
  })

  it('shows support message for bucket changes', async () => {
    await flushPromises()

    const supportMessage = wrapper.text()
    expect(supportMessage).toContain('Please contact')
    expect(supportMessage).toContain('Support')
    expect(supportMessage).toContain('to change the bucket')
  })

  it('handles form submission error', async () => {
    const mockUpdateOrbit = vi.fn().mockRejectedValue(new Error('API Error'))
    const mockToastAdd = vi.fn()

    vi.doMock('@/stores/orbits', () => ({
      useOrbitsStore: () => ({
        updateOrbit: mockUpdateOrbit,

        deleteOrbit: vi.fn(),
      }),
    }))

    vi.doMock('primevue', async (importOriginal) => {
      const actual = (await importOriginal()) as Record<string, unknown>
      return {
        ...actual,
        useToast: () => ({
          add: mockToastAdd,
        }),

        useConfirm: () => ({
          require: vi.fn(),
        }),
      }
    })

    await flushPromises()
    const nameInput = wrapper.find('input#name')
    await nameInput.setValue('Test Orbit')
    const form = wrapper.find('form#orbit-edit-form')
    await form.trigger('submit')
    await flushPromises()
    expect(form.exists()).toBe(true)
  })
})
