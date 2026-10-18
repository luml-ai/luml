import { mount, flushPromises } from '@vue/test-utils'
import OrbitCreator from './OrbitCreator.vue'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia } from 'pinia'
import { RelayKindEnum, RelayStatusEnum, type Relay } from '@/lib/api/relays/interfaces'

const ORGANIZATION_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'

function makeRelay(id: string, kind: RelayKindEnum, status: RelayStatusEnum): Relay {
  return {
    id,
    organization_id: kind === RelayKindEnum.own ? ORGANIZATION_ID : null,
    label: id,
    base_domain: `${id}.example.com`,
    agent_url: `wss://agents.${id}.example.com`,
    status,
    kind,
    online: true,
    last_seen_at: null,
    connected_agents: 0,
    capabilities: {},
    present_capabilities: [],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: null,
  }
}

const relaysStore = vi.hoisted(() => ({
  relays: [] as Relay[],
  getRelays: vi.fn(),
}))
const createOrbitMock = vi.hoisted(() => vi.fn().mockResolvedValue({}))

vi.mock('@/stores/relays', () => ({
  useRelaysStore: () => relaysStore,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' } }),
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
            id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
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
    createOrbit: createOrbitMock,
    orbitsList: [],
  }),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    getUserId: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
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
  let wrapper: ReturnType<typeof mount>
  const pinia = createPinia()

  function mountCreator() {
    return mount(OrbitCreator, {
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
            template:
              '<div><select :id="id" :name="name" @change="$emit(\'update:modelValue\', $event.target.value || null)">' +
              '<option value=""></option>' +
              '<option v-for="opt in options" :key="opt[optionValue]" :value="opt[optionValue]">{{ opt[optionLabel] }}</option>' +
              '</select><slot name="footer"></slot></div>',
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
            template: '<a :data-route="to.name" :class="className"><slot></slot></a>',
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
          $route: { params: { organizationId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' } },
        },
      },
      props: {
        visible: true,
        organizationId: ORGANIZATION_ID,
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    relaysStore.relays = [
      makeRelay('lab', RelayKindEnum.own, RelayStatusEnum.enabled),
      makeRelay('old', RelayKindEnum.own, RelayStatusEnum.draining),
      makeRelay('eu', RelayKindEnum.managed, RelayStatusEnum.enabled),
    ]
    wrapper = mountCreator()
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

  it('lists enabled relays by label with managed ones marked', async () => {
    await flushPromises()
    const options = wrapper.findAll('select#relay option').map((option) => option.text())
    expect(options).toEqual(['', 'lab', 'eu (managed)'])
  })

  it('may be left without a relay', async () => {
    await flushPromises()
    await wrapper.find('input[name="name"]').setValue('Test Orbit')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createOrbitMock).toHaveBeenCalledWith(
      ORGANIZATION_ID,
      expect.objectContaining({ relay_id: null }),
    )
  })

  it('creates the orbit with the chosen relay', async () => {
    await flushPromises()
    await wrapper.find('input[name="name"]').setValue('Test Orbit')
    await wrapper.find('select#relay').setValue('eu')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createOrbitMock).toHaveBeenCalledWith(
      ORGANIZATION_ID,
      expect.objectContaining({ relay_id: 'eu' }),
    )
  })

  it('loads relays when opened', async () => {
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    expect(relaysStore.getRelays).toHaveBeenCalledWith(ORGANIZATION_ID)
  })

  it('points to the relays tab when no relay can be used', async () => {
    wrapper.unmount()
    relaysStore.relays = [makeRelay('old', RelayKindEnum.own, RelayStatusEnum.draining)]
    wrapper = mountCreator()
    await flushPromises()
    expect(wrapper.findAll('select#relay option')).toHaveLength(1)
    expect(wrapper.text()).toContain('Add a relay')
    expect(wrapper.find('a[data-route="organization-relays"]').exists()).toBe(true)
  })

  it('shows no relays hint while a relay can be used', async () => {
    await flushPromises()
    expect(wrapper.text()).not.toContain('Add a relay')
  })
})
