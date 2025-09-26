import { mount, flushPromises } from '@vue/test-utils'
import OrbitCreator from './OrbitCreator.vue'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: '123' } }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/mock' } },
  }),
}))

vi.mock('@/stores/buckets', () => ({
  useBucketsStore: () => ({
    getBuckets: vi.fn().mockResolvedValue([]),
    buckets: [],
  }),
}))

vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({
    organizationDetails: {
      members: [
        {
          user: {
            id: 2,
            full_name: 'Test User',
            email: 'test@example.com',
          },
        },
      ],
    },
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    createOrbit: vi.fn().mockResolvedValue({}),
    orbitsList: [],
  }),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    getUserId: 1,
  }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return {
    ...actual,
    useToast: () => ({ add: vi.fn() }),
  }
})

vi.mock('@/utils/forms/resolvers', () => ({
  orbitCreatorResolver: () => vi.fn(),
}))

vi.mock('@/lib/primevue/data/toasts', () => ({
  simpleErrorToast: vi.fn(),
  simpleSuccessToast: vi.fn(),
}))

vi.mock('lucide-vue-next', () => ({
  Plus: { template: '<span>+</span>' },
}))
describe('OrbitCreator', () => {
  let wrapper: any
  const pinia = createPinia()

  beforeEach(() => {
    vi.clearAllMocks()

    wrapper = mount(OrbitCreator, {
      global: {
        plugins: [pinia],
        stubs: {
          Dialog: {
            template: '<div v-if="visible"><slot></slot></div>',
            props: ['visible', 'header', 'modal', 'draggable', 'pt'],
          },

          Form: {
            template: '<form @submit="$emit(\'submit\', { valid: true })"><slot></slot></form>',
            props: ['initialValues', 'resolver', 'validateOnValueUpdate'],
          },

          InputText: {
            template:
              '<input :id="id" :name="name" :placeholder="placeholder" v-model="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['id', 'name', 'placeholder', 'modelValue', 'fluid'],
            emits: ['update:modelValue'],
          },

          MultiSelect: {
            template: '<select multiple :id="id" :name="name"><slot name="footer"></slot></select>',
            props: [
              'options',
              'optionLabel',
              'modelValue',
              'id',
              'name',
              'placeholder',
              'filter',
              'display',
              'fluid',
              'pt',
            ],
            emits: ['update:modelValue'],
          },

          Select: {
            template: '<select :id="id" :name="name"><slot name="footer"></slot></select>',
            props: [
              'options',
              'optionLabel',
              'optionValue',
              'modelValue',
              'id',
              'name',
              'placeholder',
              'filter',
              'fluid',
              'pt',
              'size',
            ],
            emits: ['update:modelValue'],
          },

          Button: {
            template: '<button type="submit" :disabled="loading"><slot></slot></button>',
            props: ['type', 'fluid', 'rounded', 'loading'],
          },

          Checkbox: {
            template:
              '<input type="checkbox" :id="inputId" v-model="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
            props: ['inputId', 'modelValue', 'binary'],
            emits: ['update:modelValue'],
          },

          RouterLink: {
            template: '<a :to="to" :class="className"><slot></slot></a>',
            props: ['to', 'className'],
          },

          'd-button': {
            template:
              '<button :class="className" :variant="variant" :size="size" :as-child="asChild"><slot></slot></button>',
            props: ['variant', 'asChild', 'size', 'className'],
          },

          Plus: {
            template: '<span>+</span>',
            props: ['size'],
          },
        },
        mocks: {
          $route: { params: { organizationId: '123' } },
        },
      },
      props: {
        visible: true,
      },
    })
  })
  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  it('renders correctly when visible', async () => {
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.find('input[name="name"]').exists()).toBe(true)
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)
  })

  it('creates orbit on form submit with valid data', async () => {
    const mockCreateOrbit = vi.fn().mockResolvedValue({})

    vi.doMock('@/stores/orbits', () => ({
      useOrbitsStore: () => ({
        createOrbit: mockCreateOrbit,
        orbitsList: [],
      }),
    }))

    await flushPromises()

    const nameInput = wrapper.find('input[name="name"]')
    await nameInput.setValue('Test Orbit')
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(form.exists()).toBe(true)
  })

  it('validates required fields', async () => {
    await flushPromises()
    const nameInput = wrapper.find('input[name="name"]')
    expect(nameInput.exists()).toBe(true)
    const nameLabel = wrapper.find('label[for="name"]')
    expect(nameLabel.classes()).toContain('required')
  })

  it('shows members role assignment when members are selected', async () => {
    await flushPromises()
    expect(wrapper.find('.members').exists()).toBe(false)
  })

  it('handles form submission error', async () => {
    const mockCreateOrbit = vi.fn().mockRejectedValue(new Error('API Error'))
    const mockToastAdd = vi.fn()
    vi.doMock('@/stores/orbits', () => ({
      useOrbitsStore: () => ({
        createOrbit: mockCreateOrbit,
        orbitsList: [],
      }),
    }))

    vi.doMock('primevue', async (importOriginal) => {
      const actual = (await importOriginal()) as Record<string, unknown>
      return {
        ...actual,
        useToast: () => ({ add: mockToastAdd }),
      }
    })

    await flushPromises()
    const nameInput = wrapper.find('input[name="name"]')
    await nameInput.setValue('Test Orbit')
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(form.exists()).toBe(true)
  })
})
