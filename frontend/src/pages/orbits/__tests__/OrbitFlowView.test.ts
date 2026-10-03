import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import OrbitFlowView from '../OrbitFlowView.vue'
import { LiveSessionStatusEnum } from '@/lib/api/live-sessions/interfaces'
import type { Flow } from '@/lib/api/flows/interfaces'
import type { LocalFlow } from '@/utils/services/LocalStorageService.interfaces'

const ORG = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT = '0199c8cf-4d35-783b-9f81-cb3cec788074'
const LAUNCH_URL = 'https://k3j9x2.tunnel.example/_luml/launch?token=t'

const flowsApi = vi.hoisted(() => ({ getList: vi.fn(), remove: vi.fn() }))
const liveSessionsApi = vi.hoisted(() => ({ issueViewToken: vi.fn() }))
const toastAdd = vi.hoisted(() => vi.fn())
const confirmRequire = vi.hoisted(() => vi.fn())
const orbitsStore = vi.hoisted(() => ({
  currentOrbitDetails: { relay_id: 'relay-1' as string | null },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: ORG, id: ORBIT } }),
}))
vi.mock('@/lib/api', () => ({ api: { flows: flowsApi, liveSessions: liveSessionsApi } }))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => orbitsStore }))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: toastAdd }),
  useConfirm: () => ({ require: confirmRequire }),
}))

const stubs = {
  DButton: {
    props: ['label'],
    emits: ['click'],
    template: '<button v-bind="$attrs" @click="$emit(\'click\')">{{ label }}</button>',
  },
  Button: {
    props: ['label', 'type', 'loading'],
    emits: ['click'],
    template:
      '<button :type="type || \'button\'" @click="$emit(\'click\')"><slot name="icon" />{{ label }}</button>',
  },
  Skeleton: { template: '<div data-testid="skeleton" />' },
  Dialog: {
    props: ['visible', 'header'],
    template: '<div v-if="visible" class="dialog">{{ header }}<slot /></div>',
  },
  InputText: {
    props: ['modelValue', 'id'],
    emits: ['update:modelValue'],
    template:
      '<input :id="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  InputNumber: {
    props: ['modelValue', 'inputId'],
    emits: ['update:modelValue'],
    template:
      '<input :id="inputId" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
  RouterLink: {
    props: ['to'],
    template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
  },
}

let reachablePorts: Set<number>

function fetchLumlflow(url: string) {
  const port = Number(new URL(url).port)
  if (!reachablePorts.has(port)) return Promise.reject(new TypeError('Failed to fetch'))
  return Promise.resolve({ ok: true })
}

function relayedFlow(overrides: Partial<Flow['session']> = {}, name = 'training'): Flow {
  return {
    id: `flow-${name}`,
    orbit_id: ORBIT,
    user_id: 'user-1',
    name,
    created_at: '2026-10-03T10:00:00Z',
    session: {
      id: 'k3j9x2',
      status: LiveSessionStatusEnum.live,
      started_at: '2026-10-03T10:00:00Z',
      last_heartbeat_at: '2026-10-03T10:00:30Z',
      ...overrides,
    },
  }
}

function saveLocalFlows(flows: LocalFlow[]) {
  localStorage.setItem('localFlows', JSON.stringify(flows))
}

async function mountView() {
  const wrapper = mount(OrbitFlowView, {
    global: { stubs, directives: { tooltip: () => undefined } },
  })
  await flushPromises()
  return wrapper
}

function localCards(wrapper: VueWrapper) {
  return wrapper.findAll('[data-testid="flow-card-local"]')
}

function relayedCards(wrapper: VueWrapper) {
  return wrapper.findAll('[data-testid="flow-card-relayed"]')
}

async function openAddDialog(wrapper: VueWrapper) {
  await wrapper.get('[data-testid="add-flow"]').trigger('click')
}

async function addLocalFlow(wrapper: VueWrapper, port: number, name = '') {
  await wrapper.get('[data-testid="choice-local"]').trigger('click')
  await wrapper.get('#flow-port').setValue(String(port))
  await wrapper.get('#flow-name').setValue(name)
  await wrapper.get('[data-testid="local-form"]').trigger('submit')
  await flushPromises()
}

describe('OrbitFlowView', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    reachablePorts = new Set()
    vi.stubGlobal('fetch', vi.fn(fetchLumlflow))
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    flowsApi.getList.mockResolvedValue([])
    flowsApi.remove.mockResolvedValue(undefined)
    orbitsStore.currentOrbitDetails = { relay_id: 'relay-1' }
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the plus card when there are no flows, and both open the two choices', async () => {
    const wrapper = await mountView()

    expect(flowsApi.getList).toHaveBeenCalledWith(ORG, ORBIT)
    expect(localCards(wrapper)).toHaveLength(0)
    expect(relayedCards(wrapper)).toHaveLength(0)

    await wrapper.get('.card button').trigger('click')
    expect(wrapper.find('[data-testid="choice-local"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="choice-relayed"]').exists()).toBe(true)
  })

  it('opens the two choices from the header button', async () => {
    const wrapper = await mountView()

    await openAddDialog(wrapper)

    expect(wrapper.find('[data-testid="choice-local"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="choice-relayed"]').exists()).toBe(true)
  })

  it('shows local flows first and marks each card local or relayed', async () => {
    saveLocalFlows([
      { name: 'first', address: 'localhost', port: 5000 },
      { name: 'second', address: 'localhost', port: 5001 },
    ])
    reachablePorts = new Set([5000, 5001, 5002])
    flowsApi.getList.mockResolvedValue([relayedFlow()])
    const wrapper = await mountView()

    await openAddDialog(wrapper)
    await addLocalFlow(wrapper, 5002)

    const cards = wrapper.findAll('[data-testid^="flow-card-"]')
    expect(cards.map((card) => card.get('[data-testid="flow-kind"]').text())).toEqual([
      'Local',
      'Local',
      'Local',
      'Relayed',
    ])
    expect(localCards(wrapper)[2]!.text()).toContain('localhost:5002')

    await openAddDialog(wrapper)
    await addLocalFlow(wrapper, 5000)

    expect(wrapper.get('[data-testid="local-error"]').text()).toBe(
      'localhost:5000 is already on the page as "first".',
    )
    expect(wrapper.findAll('[data-testid^="flow-card-"]')).toHaveLength(4)
  })

  it('adds a reachable local flow that opens lumlflow in a new tab', async () => {
    reachablePorts = new Set([5000])
    const wrapper = await mountView()

    await openAddDialog(wrapper)
    await addLocalFlow(wrapper, 5000)

    expect(fetch).toHaveBeenCalledWith('http://localhost:5000/api/auth/status', expect.anything())
    expect(JSON.parse(localStorage.getItem('localFlows')!)).toEqual([
      { name: 'localhost:5000', address: 'localhost', port: 5000 },
    ])
    const card = localCards(wrapper)[0]!
    expect(card.get('.status').classes()).toContain('status--success')
    const openLink = card.get('[data-testid="open-flow"]')
    expect(openLink.attributes('href')).toBe('http://localhost:5000')
    expect(openLink.attributes('target')).toBe('_blank')
    expect(wrapper.find('.dialog').exists()).toBe(false)
  })

  it('shows the local flows saved in the browser', async () => {
    saveLocalFlows([{ name: 'mine', address: 'localhost', port: 5000 }])
    const wrapper = await mountView()

    expect(localCards(wrapper)).toHaveLength(1)
    expect(localCards(wrapper)[0]!.text()).toContain('mine')
  })

  it('saves nothing when the local address does not answer', async () => {
    const wrapper = await mountView()

    await openAddDialog(wrapper)
    await addLocalFlow(wrapper, 5000)

    expect(wrapper.get('[data-testid="local-error"]').text()).toBe(
      'localhost:5000 did not answer. Only localhost is reliably reachable from this page, in a browser that allows it.',
    )
    expect(localStorage.getItem('localFlows')).toBeNull()
    expect(localCards(wrapper)).toHaveLength(0)
  })

  it('keeps an offline local card and shows it reachable again on the next refresh', async () => {
    saveLocalFlows([{ name: 'mine', address: 'localhost', port: 5000 }])
    const wrapper = await mountView()

    const card = () => localCards(wrapper)[0]!
    expect(card().get('.status').classes()).toContain('status--danger')
    expect(card().text()).toContain('Not answering right now')
    expect(card().get('[data-testid="flow-kind"]').text()).toBe('Local')

    reachablePorts.add(5000)
    vi.advanceTimersByTime(10_000)
    await flushPromises()

    expect(card().get('.status').classes()).toContain('status--success')
  })

  it('removes a local flow from local storage', async () => {
    saveLocalFlows([{ name: 'mine', address: 'localhost', port: 5000 }])
    const wrapper = await mountView()

    await localCards(wrapper)[0]!.get('[data-testid="remove-flow"]').trigger('click')

    expect(localCards(wrapper)).toHaveLength(0)
    expect(JSON.parse(localStorage.getItem('localFlows')!)).toEqual([])
  })

  it('links the relayed choice to the docs page when the orbit has a relay', async () => {
    const wrapper = await mountView()

    await openAddDialog(wrapper)
    await wrapper.get('[data-testid="choice-relayed"]').trigger('click')

    const info = wrapper.get('[data-testid="relayed-info"]')
    expect(info.text()).toContain('exposed from the machine where it runs')
    expect(info.get('[data-testid="docs-link"]').attributes('href')).toMatch(
      /\/apps\/lumlflow\/relayed_flows$/,
    )
    expect(info.find('[data-testid="orbits-link"]').exists()).toBe(false)
  })

  it('links the relayed choice to the orbits tab when the orbit has no relay', async () => {
    orbitsStore.currentOrbitDetails = { relay_id: null }
    const wrapper = await mountView()

    await openAddDialog(wrapper)
    await wrapper.get('[data-testid="choice-relayed"]').trigger('click')

    const info = wrapper.get('[data-testid="relayed-info"]')
    expect(info.text()).toContain('This orbit has no relay')
    expect(JSON.parse(info.get('[data-testid="orbits-link"]').attributes('data-to')!)).toEqual({
      name: 'organization-orbits',
      params: { organizationId: ORG },
    })
    expect(info.find('[data-testid="docs-link"]').exists()).toBe(false)
  })

  it('opens a live relayed flow in a tab opened on the click', async () => {
    flowsApi.getList.mockResolvedValue([relayedFlow()])
    const tab = { opener: {}, location: { href: '' }, close: vi.fn() }
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    let resolveToken!: (value: { launch_url: string }) => void
    liveSessionsApi.issueViewToken.mockReturnValue(
      new Promise((resolve) => {
        resolveToken = resolve
      }),
    )
    const wrapper = await mountView()

    await relayedCards(wrapper)[0]!.get('[data-testid="open-flow"]').trigger('click')

    expect(openSpy).toHaveBeenCalledWith('', '_blank')
    expect(tab.opener).toBeNull()
    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledWith(ORG, ORBIT, 'k3j9x2')

    resolveToken({ launch_url: LAUNCH_URL })
    await flushPromises()
    expect(tab.location.href).toBe(LAUNCH_URL)
    openSpy.mockRestore()
  })

  it('closes the tab and reports the error when viewer access is refused', async () => {
    flowsApi.getList.mockResolvedValue([relayedFlow()])
    const tab = { opener: {}, location: { href: '' }, close: vi.fn() }
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    liveSessionsApi.issueViewToken.mockRejectedValue({
      response: { data: { detail: 'Live session not found' } },
    })
    const wrapper = await mountView()

    await relayedCards(wrapper)[0]!.get('[data-testid="open-flow"]').trigger('click')
    await flushPromises()

    expect(tab.close).toHaveBeenCalled()
    expect(toastAdd).toHaveBeenCalled()
    openSpy.mockRestore()
  })

  it('removes a relayed flow after a confirmation', async () => {
    flowsApi.getList.mockResolvedValue([relayedFlow()])
    const wrapper = await mountView()

    await relayedCards(wrapper)[0]!.get('[data-testid="remove-flow"]').trigger('click')
    expect(flowsApi.remove).not.toHaveBeenCalled()

    confirmRequire.mock.calls[0]![0].accept()
    await flushPromises()

    expect(flowsApi.remove).toHaveBeenCalledWith(ORG, ORBIT, 'flow-training')
    expect(relayedCards(wrapper)).toHaveLength(0)
  })

  it('offers no open action on a disconnected flow and shows its last heartbeat', async () => {
    const lastHeartbeat = '2026-10-03T09:00:00Z'
    flowsApi.getList.mockResolvedValue([
      relayedFlow({
        status: LiveSessionStatusEnum.disconnected,
        last_heartbeat_at: lastHeartbeat,
      }),
    ])
    const wrapper = await mountView()

    const card = relayedCards(wrapper)[0]!
    expect(card.find('[data-testid="open-flow"]').exists()).toBe(false)
    expect(card.get('.status').classes()).toContain('status--warn')
    expect(card.get('[data-testid="flow-heartbeat"]').text()).toBe(
      `Last heartbeat at ${new Date(lastHeartbeat).toLocaleString()}`,
    )
  })

  it('refreshes relayed flows on the interval and stops when left', async () => {
    const wrapper = await mountView()
    flowsApi.getList.mockResolvedValue([relayedFlow()])

    vi.advanceTimersByTime(10_000)
    await flushPromises()
    expect(relayedCards(wrapper)).toHaveLength(1)

    wrapper.unmount()
    flowsApi.getList.mockClear()
    vi.advanceTimersByTime(10_000)
    expect(flowsApi.getList).not.toHaveBeenCalled()
  })
})
