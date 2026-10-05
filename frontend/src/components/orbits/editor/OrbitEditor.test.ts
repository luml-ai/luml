import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia } from 'pinia'
import OrbitSettingsDialog from './OrbitEditor.vue'
import { OrbitRoleEnum } from '../orbits.interfaces'
import { PermissionEnum, type Orbit } from '@/lib/api/api.interfaces'
import { RelayKindEnum, RelayStatusEnum, type Relay } from '@/lib/api/relays/interfaces'

const ORGANIZATION_ID = 'org-1111-aaaa-bbbb-cccc-000000000001'

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

vi.mock('@/stores/relays', () => ({
  useRelaysStore: () => relaysStore,
}))

const updateOrbitMock = vi.fn().mockResolvedValue({})
const deleteOrbitMock = vi.fn().mockResolvedValue({})
const toastAddMock = vi.fn()
const confirmRequireMock = vi.fn()

vi.mock('@/stores/buckets', () => ({
  useBucketsStore: () => ({
    buckets: [{ id: 'bucket-1111-aaaa-bbbb-cccc-000000000001', bucket_name: 'Bucket One' }],
    getBuckets: vi.fn(),
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    updateOrbit: updateOrbitMock,
    deleteOrbit: deleteOrbitMock,
  }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return {
    ...actual,
    useToast: () => ({ add: toastAddMock }),
    useConfirm: () => ({ require: confirmRequireMock }),
  }
})

vi.mock('@/lib/primevue/data/toasts', () => ({
  simpleErrorToast: vi.fn((msg: string) => ({ severity: 'error', summary: msg })),
  simpleSuccessToast: vi.fn((msg: string) => ({ severity: 'success', summary: msg })),
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
  Plus: { template: '<span>+</span>' },
}))

describe('OrbitSettingsDialog', () => {
  let wrapper: ReturnType<typeof mount>

  const pinia = createPinia()

  const orbit: Orbit = {
    id: 'orbit-aaaa-bbbb-cccc-dddd-000000000001',
    name: 'Test Orbit',
    organization_id: ORGANIZATION_ID,
    total_members: 10,
    created_at: new Date(),
    updated_at: null,
    bucket_secret_id: 'bucket-1111-aaaa-bbbb-cccc-000000000001',
    relay_id: 'old',
    total_collections: 5,
    role: OrbitRoleEnum.member,
    total_artifacts: 0,
    permissions: {
      orbit: PermissionEnum.delete,
      orbit_user: PermissionEnum.read,
      artifact: PermissionEnum.create,
      collection: PermissionEnum.create,
      track: PermissionEnum.create,
    },
  }

  function mountEditor() {
    return mount(OrbitSettingsDialog, {
      global: {
        plugins: [pinia],

        stubs: {
          Dialog: {
            template:
              '<div v-if="visible"><slot name="header"></slot><slot></slot><slot name="footer"></slot></div>',
            props: ['visible', 'position', 'draggable', 'pt'],
          },

          Form: {
            template: '<form id="orbit-edit-form" @submit.prevent="onSubmit"><slot></slot></form>',
            props: ['id', 'initialValues', 'resolver'],
            emits: ['submit'],
            data() {
              return {
                values: { ...(this.initialValues || {}) },
              }
            },
            provide() {
              return {
                formValues: this.values,
                setFormValue: (name: string, value: unknown) => {
                  this.values[name] = value
                },
              }
            },
            methods: {
              onSubmit() {
                this.$emit('submit', { valid: true, values: { ...this.values } })
              },
            },
          },
          InputText: {
            template: '<input :id="id" :name="name" :value="localValue" @input="onInput" />',
            props: ['id', 'name'],
            inject: {
              formValues: { default: () => ({}) },
              setFormValue: { default: () => () => {} },
            },
            computed: {
              localValue(): string {
                return this.formValues?.[this.name] ?? ''
              },
            },
            methods: {
              onInput(e: Event) {
                this.setFormValue(this.name, (e.target as HTMLInputElement).value)
              },
            },
          },
          Select: {
            template:
              '<div><select :id="id" :name="name" :disabled="disabled" :value="localValue" @change="onChange">' +
              '<option value=""></option>' +
              '<option v-for="opt in options" :key="opt[optionValue]" :value="opt[optionValue]">{{ opt[optionLabel] }}</option>' +
              '</select><slot name="footer"></slot></div>',
            props: [
              'options',
              'optionLabel',
              'optionValue',
              'id',
              'name',
              'disabled',
              'defaultValue',
            ],
            inject: {
              formValues: { default: () => ({}) },
              setFormValue: { default: () => () => {} },
            },
            computed: {
              localValue(): string {
                return this.formValues?.[this.name] ?? this.defaultValue ?? ''
              },
            },
            methods: {
              onChange(e: Event) {
                this.setFormValue(this.name, (e.target as HTMLSelectElement).value || null)
              },
            },
          },
          RouterLink: {
            template: '<a :data-route="to.name"><slot></slot></a>',
            props: ['to'],
          },
          'd-button': {
            template: '<span><slot :class="\'\'"></slot></span>',
          },
          Button: {
            template:
              '<button :type="type" :form="form" :disabled="disabled || loading" :variant="variant" :severity="severity" @click="$emit(\'click\', $event)"><slot></slot></button>',
            props: ['type', 'form', 'loading', 'disabled', 'variant', 'severity'],
            emits: ['click'],
          },
        },
      },

      props: {
        orbit,
        visible: true,
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
    wrapper = mountEditor()
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  it('renders dialog with initial values', async () => {
    await flushPromises()
    expect(wrapper.find('input#name').exists()).toBe(true)
    expect((wrapper.find('input#name').element as HTMLInputElement).value).toBe('Test Orbit')
    expect(wrapper.find('select#bucket').exists()).toBe(true)
    expect((wrapper.find('select#bucket').element as HTMLSelectElement).value).toBe(
      'bucket-1111-aaaa-bbbb-cccc-000000000001',
    )
  })

  it('submits form and calls updateOrbit with edited values', async () => {
    await flushPromises()
    const nameInput = wrapper.find('input#name')
    await nameInput.setValue('New Orbit Name')
    const form = wrapper.find('form#orbit-edit-form')
    await form.trigger('submit')
    await flushPromises()

    expect(updateOrbitMock).toHaveBeenCalledTimes(1)
    expect(updateOrbitMock).toHaveBeenCalledWith(
      orbit.organization_id,
      expect.objectContaining({
        id: orbit.id,
        name: 'New Orbit Name',
        bucket_secret_id: orbit.bucket_secret_id,
      }),
    )
    expect(toastAddMock).toHaveBeenCalled()
  })

  it('shows delete button when user has delete permission', async () => {
    await flushPromises()

    const deleteButton = wrapper.find('button[severity="warn"]')
    expect(deleteButton.exists()).toBe(true)
    expect(deleteButton.attributes().label).toBe('Delete Orbit')
  })

  it('handles delete orbit action', async () => {
    await flushPromises()
    const deleteButton = wrapper.find('button[severity="warn"]')
    await deleteButton.trigger('click')
    await flushPromises()
    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const confirmOptions = confirmRequireMock.mock.calls[0][0]
    await confirmOptions.accept()
    await flushPromises()

    expect(deleteOrbitMock).toHaveBeenCalledWith(orbit.organization_id, orbit.id)
  })

  it('disables bucket select field', async () => {
    await flushPromises()

    const bucketSelect = wrapper.find('select#bucket')
    expect(bucketSelect.exists()).toBe(true)
    expect(bucketSelect.attributes('disabled')).toBeDefined()
  })

  it('shows support message for bucket changes', async () => {
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Please contact')
    expect(text).toContain('Support')
    expect(text).toContain('to change the bucket')
  })

  it('handles form submission error', async () => {
    updateOrbitMock.mockRejectedValueOnce(new Error('API Error'))

    await flushPromises()
    const form = wrapper.find('form#orbit-edit-form')
    await form.trigger('submit')
    await flushPromises()

    expect(updateOrbitMock).toHaveBeenCalled()
    expect(toastAddMock).toHaveBeenCalled()
  })

  it('shows the assigned draining relay as the current value marked as draining', async () => {
    await flushPromises()
    const relaySelect = wrapper.find('select#relay')
    const options = relaySelect.findAll('option').map((option) => option.text())
    expect(options).toEqual(['', 'lab', 'old (draining)', 'eu (managed)'])
    expect((relaySelect.element as HTMLSelectElement).value).toBe('old')
    expect(relaySelect.attributes('disabled')).toBeUndefined()
  })

  it('hides draining relays that are not assigned', async () => {
    await wrapper.setProps({ orbit: { ...orbit, relay_id: null } })
    await flushPromises()
    const options = wrapper.findAll('select#relay option').map((option) => option.text())
    expect(options).toEqual(['', 'lab', 'eu (managed)'])
  })

  it('saves a changed relay', async () => {
    await flushPromises()
    await wrapper.find('select#relay').setValue('eu')
    await wrapper.find('form#orbit-edit-form').trigger('submit')
    await flushPromises()
    expect(updateOrbitMock).toHaveBeenCalledWith(
      ORGANIZATION_ID,
      expect.objectContaining({ id: orbit.id, relay_id: 'eu' }),
    )
  })

  it('clears the relay', async () => {
    await flushPromises()
    await wrapper.find('select#relay').setValue('')
    await wrapper.find('form#orbit-edit-form').trigger('submit')
    await flushPromises()
    expect(updateOrbitMock).toHaveBeenCalledWith(
      ORGANIZATION_ID,
      expect.objectContaining({ id: orbit.id, relay_id: null }),
    )
  })

  it('loads relays when mounted already open on an empty store', () => {
    wrapper.unmount()
    vi.clearAllMocks()
    relaysStore.relays = []
    wrapper = mountEditor()
    expect(relaysStore.getRelays).toHaveBeenCalledOnce()
    expect(relaysStore.getRelays).toHaveBeenCalledWith(ORGANIZATION_ID)
  })

  it('loads relays when reopened', async () => {
    await wrapper.setProps({ visible: false })
    vi.clearAllMocks()
    await wrapper.setProps({ visible: true })
    expect(relaysStore.getRelays).toHaveBeenCalledWith(ORGANIZATION_ID)
  })

  it('points to the relays tab when no relay can be used', async () => {
    wrapper.unmount()
    relaysStore.relays = []
    wrapper = mountEditor()
    await flushPromises()
    expect(wrapper.text()).toContain('Add a relay')
    expect(wrapper.find('a[data-route="organization-relays"]').exists()).toBe(true)
  })
})
