import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { RelayKindEnum, RelayStatusEnum, type Relay } from '@/lib/api/relays/interfaces'
import { useRelaysStore } from '@/stores/relays'
import OrganizationRelays from './OrganizationRelays.vue'
import RelayTokenDialog from './RelayTokenDialog.vue'

const relaysApi = vi.hoisted(() => ({
  getRelays: vi.fn(),
  createRelay: vi.fn(),
  updateRelay: vi.fn(),
  rotateRelayToken: vi.fn(),
  deleteRelay: vi.fn(),
}))
const organizationStore = vi.hoisted(() => ({
  currentOrganization: { id: 'org-1', permissions: { relay: [] as string[] } },
}))
const toastAdd = vi.hoisted(() => vi.fn())
const confirmRequire = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({ api: { relays: relaysApi } }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: toastAdd }),
  useConfirm: () => ({ require: confirmRequire }),
}))

const stubs = {
  Button: {
    props: ['label', 'type', 'form', 'disabled', 'loading'],
    emits: ['click'],
    template:
      '<button :type="type || \'button\'" :form="form" :disabled="disabled" @click="$emit(\'click\')"><slot name="icon" />{{ label }}<slot /></button>',
  },
  InputText: {
    props: ['modelValue', 'value', 'id', 'name'],
    emits: ['update:modelValue'],
    template:
      '<input :id="id" :name="name" :value="modelValue ?? value" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  Dialog: {
    props: ['visible', 'header'],
    emits: ['update:visible'],
    template:
      '<div v-if="visible" class="dialog">{{ header }}<slot name="header" /><slot /><slot name="footer" /></div>',
  },
  UiDialogRight: {
    props: ['visible', 'footerActions'],
    template: `<div v-if="visible" class="right-dialog">
      <slot />
      <button class="remove" @click="footerActions.leftButton.props.onClick">remove</button>
    </div>`,
  },
  ToggleSwitch: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" class="toggle" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
  },
  Tag: { props: ['value'], template: '<span class="tag">{{ value }}</span>' },
  InputGroup: { template: '<div><slot /></div>' },
  InputGroupAddon: { template: '<div><slot /></div>' },
}

function relay(overrides: Partial<Relay> = {}): Relay {
  return {
    id: 'relay-own',
    organization_id: 'org-1',
    label: 'lab',
    base_domain: 'tunnel.lab.example',
    agent_url: 'wss://tunnel.lab.example',
    status: RelayStatusEnum.enabled,
    kind: RelayKindEnum.own,
    online: false,
    last_seen_at: null,
    connected_agents: 0,
    capabilities: {},
    present_capabilities: [],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

const managedRelay = relay({
  id: 'relay-eu',
  organization_id: null,
  label: 'eu',
  base_domain: 'eu.relay.example',
  agent_url: 'wss://eu.relay.example',
  kind: RelayKindEnum.managed,
  online: true,
  last_seen_at: '2026-10-03T10:00:00Z',
  connected_agents: 3,
  capabilities: { sessions: { version: 1, api_versions: [1] } },
  present_capabilities: ['sessions'],
})

const ownerPermissions = [
  PermissionEnum.list,
  PermissionEnum.read,
  PermissionEnum.create,
  PermissionEnum.update,
  PermissionEnum.delete,
]

async function mountTab(permissions: string[] = ownerPermissions) {
  organizationStore.currentOrganization.permissions.relay = permissions
  const wrapper = mount(OrganizationRelays, { global: { stubs, directives: { tooltip: {} } } })
  await flushPromises()
  return wrapper
}

function rows(wrapper: VueWrapper) {
  return wrapper.findAll('[data-test="relay-row"]')
}

function apiError(detail: string) {
  return { response: { data: { detail } } }
}

const lastToast = () => toastAdd.mock.calls.at(-1)?.[0]

describe('OrganizationRelays', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    relaysApi.getRelays.mockResolvedValue([relay(), managedRelay])
    Object.assign(navigator, { clipboard: { writeText: vi.fn() } })
  })

  it('lists own and managed relays with kind, status and sessions', async () => {
    const wrapper = await mountTab()

    expect(relaysApi.getRelays).toHaveBeenCalledWith('org-1')
    expect(wrapper.text()).toContain('(2)')
    const [own, managed] = rows(wrapper)
    expect(own?.text()).toContain('lab')
    expect(own?.text()).toContain('Own')
    expect(own?.text()).toContain('Offline')
    expect(own?.text()).not.toContain('Draining')
    expect(own?.find('[aria-label="Relay settings"]').exists()).toBe(true)
    expect(managed?.text()).toContain('Managed')
    expect(managed?.text()).toContain('Online')
    expect(managed?.text()).toContain('3')
    expect(managed?.find('[aria-label="Relay settings"]').exists()).toBe(false)
  })

  it('marks only the relays that report the sessions capability', async () => {
    const wrapper = await mountTab()

    const [own, managed] = rows(wrapper)
    expect(own?.find('[data-test="sessions-capability"]').exists()).toBe(false)
    expect(managed?.find('[data-test="sessions-capability"]').exists()).toBe(true)
  })

  it('hides the add button and the settings without the permissions to change relays', async () => {
    const wrapper = await mountTab([PermissionEnum.list, PermissionEnum.read])

    expect(wrapper.text()).not.toContain('New relay')
    expect(wrapper.find('[aria-label="Relay settings"]').exists()).toBe(false)
  })

  it('adds a relay and shows its token once', async () => {
    const created = relay({ id: 'relay-new', label: 'new' })
    relaysApi.createRelay.mockResolvedValue({ relay: created, token: 'dfsrelay_' + 'x'.repeat(40) })
    const wrapper = await mountTab()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'New relay')
      ?.trigger('click')
    await wrapper.find('#relayCreateForm-label').setValue('new')
    await wrapper.find('#relayCreateForm-base-domain').setValue('tunnel.new.example')
    await wrapper.find('#relayCreateForm-agent-url').setValue('wss://tunnel.new.example')
    await wrapper.find('form#relayCreateForm').trigger('submit')
    await flushPromises()

    expect(relaysApi.createRelay).toHaveBeenCalledWith('org-1', {
      label: 'new',
      base_domain: 'tunnel.new.example',
      agent_url: 'wss://tunnel.new.example',
    })
    expect(rows(wrapper)).toHaveLength(3)
    const tokenDialog = wrapper.findComponent(RelayTokenDialog)
    expect(tokenDialog.exists()).toBe(true)
    expect(tokenDialog.text()).toContain('dfsrelay_')
    expect(tokenDialog.text()).toContain('LUML_TUNNEL_RELAY_TOKEN=')

    tokenDialog.vm.$emit('close')
    await flushPromises()

    expect(wrapper.findComponent(RelayTokenDialog).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('dfsrelay_')
  })

  it('shows the backend message when a relay cannot be created', async () => {
    relaysApi.createRelay.mockRejectedValue(
      apiError('Connection address must be a ws or wss address'),
    )
    const wrapper = await mountTab()

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'New relay')
      ?.trigger('click')
    await wrapper.find('form#relayCreateForm').trigger('submit')
    await flushPromises()

    expect(lastToast().detail).toBe('Connection address must be a ws or wss address')
    expect(wrapper.findComponent(RelayTokenDialog).exists()).toBe(false)
    expect(rows(wrapper)).toHaveLength(2)
  })

  it('rotates the token after the confirmation and shows the new one once', async () => {
    relaysApi.rotateRelayToken.mockResolvedValue({ relay: relay(), token: 'dfsrelay_rotated' })
    const wrapper = await mountTab()

    await wrapper.find('[aria-label="Relay settings"]').trigger('click')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Rotate')
      ?.trigger('click')
    expect(relaysApi.rotateRelayToken).not.toHaveBeenCalled()
    confirmRequire.mock.calls.at(-1)?.[0].accept()
    await flushPromises()

    expect(relaysApi.rotateRelayToken).toHaveBeenCalledWith('org-1', 'relay-own')
    const tokenDialog = wrapper.findComponent(RelayTokenDialog)
    expect(tokenDialog.props('token')).toBe('dfsrelay_rotated')

    tokenDialog.vm.$emit('close')
    await flushPromises()

    expect(wrapper.findComponent(RelayTokenDialog).exists()).toBe(false)
  })

  it('sends only the changed fields and shows a refused address change', async () => {
    relaysApi.updateRelay.mockRejectedValueOnce(
      apiError(
        'Cannot change the base domain or connection address of a relay with 1 unended session',
      ),
    )
    relaysApi.updateRelay.mockResolvedValueOnce(relay({ label: 'lab-2' }))
    const wrapper = await mountTab()

    await wrapper.find('[aria-label="Relay settings"]').trigger('click')
    await wrapper.find('#relaySettingsForm-base-domain').setValue('tunnel.other.example')
    await wrapper.find('form#relaySettingsForm').trigger('submit')
    await flushPromises()

    expect(relaysApi.updateRelay).toHaveBeenLastCalledWith('org-1', 'relay-own', {
      base_domain: 'tunnel.other.example',
    })
    expect(lastToast().detail).toContain('1 unended session')
    expect(wrapper.find('.right-dialog').exists()).toBe(true)

    await wrapper.find('#relaySettingsForm-base-domain').setValue('tunnel.lab.example')
    await wrapper.find('#relaySettingsForm-label').setValue('lab-2')
    await wrapper.find('form#relaySettingsForm').trigger('submit')
    await flushPromises()

    expect(relaysApi.updateRelay).toHaveBeenLastCalledWith('org-1', 'relay-own', { label: 'lab-2' })
    expect(rows(wrapper)[0]?.text()).toContain('lab-2')
    expect(wrapper.find('.right-dialog').exists()).toBe(false)
  })

  it('sets a relay to draining', async () => {
    relaysApi.updateRelay.mockResolvedValue(relay({ status: RelayStatusEnum.draining }))
    const wrapper = await mountTab()

    await wrapper.find('[aria-label="Relay settings"]').trigger('click')
    await wrapper.find('.toggle').setValue(true)
    await flushPromises()

    expect(relaysApi.updateRelay).toHaveBeenCalledWith('org-1', 'relay-own', {
      status: RelayStatusEnum.draining,
    })
    expect(rows(wrapper)[0]?.text()).toContain('Draining')
  })

  it('shows the backend message when a removal is refused', async () => {
    relaysApi.deleteRelay.mockRejectedValue(
      apiError('Cannot remove a relay with 2 unended sessions'),
    )
    const wrapper = await mountTab()

    await wrapper.find('[aria-label="Relay settings"]').trigger('click')
    await wrapper.find('.remove').trigger('click')
    confirmRequire.mock.calls[0]?.[0].accept()
    await flushPromises()

    expect(relaysApi.deleteRelay).toHaveBeenCalledWith('org-1', 'relay-own')
    expect(lastToast().detail).toBe('Cannot remove a relay with 2 unended sessions')
    expect(rows(wrapper)).toHaveLength(2)
  })

  it('removes a relay after the confirmation', async () => {
    relaysApi.deleteRelay.mockResolvedValue(undefined)
    const wrapper = await mountTab()

    await wrapper.find('[aria-label="Relay settings"]').trigger('click')
    await wrapper.find('.remove').trigger('click')
    expect(relaysApi.deleteRelay).not.toHaveBeenCalled()
    confirmRequire.mock.calls[0]?.[0].accept()
    await flushPromises()

    expect(rows(wrapper)).toHaveLength(1)
    expect(useRelaysStore().relays.map((item) => item.id)).toEqual(['relay-eu'])
  })
})

describe('RelayTokenDialog', () => {
  const token = 'dfsrelay_' + 'a'.repeat(30) + 'TAIL01'

  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn() } })
  })

  it('shows the token masked with what the relay needs to run', () => {
    const wrapper = mount(RelayTokenDialog, { props: { token }, global: { stubs } })

    expect(wrapper.find('input').element.value).toMatch(/^dfsrelay_a\*+TAIL01$/)
    expect(wrapper.text()).toContain(`LUML_BASE_URL=${import.meta.env.VITE_API_URL}`)
    expect(wrapper.text()).toContain('ghcr.io/luml-ai/luml-tunnel-relay')
    expect(wrapper.text()).toContain('-p 8080:8080')
    expect(wrapper.text()).toContain('wildcard DNS record')
    expect(wrapper.text()).not.toContain(token)
  })

  it('copies the full token and the full command', async () => {
    const wrapper = mount(RelayTokenDialog, { props: { token }, global: { stubs } })
    const [copyToken, , copyCommand] = wrapper.findAll('button')

    await copyToken?.trigger('click')
    await copyCommand?.trigger('click')

    const writeText = vi.mocked(navigator.clipboard.writeText)
    expect(writeText).toHaveBeenNthCalledWith(1, token)
    expect(writeText.mock.calls[1]?.[0]).toContain(`LUML_TUNNEL_RELAY_TOKEN=${token}`)
    expect(writeText.mock.calls[1]?.[0]).toContain('docker run')
  })
})
