import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import OrbitFlowView from '../OrbitFlowView.vue'
import { LiveSessionStatusEnum, type LiveSession } from '@/lib/api/live-sessions/interfaces'

const ORG = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT = '0199c8cf-4d35-783b-9f81-cb3cec788074'

const store = reactive({
  sessionsList: [] as LiveSession[],
  notConfigured: false,
  loadSessions: vi.fn(),
})

const toast = { add: vi.fn() }

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: ORG, id: ORBIT } }),
}))

vi.mock('primevue', () => ({
  Skeleton: { template: '<div data-testid="skeleton" />' },
  useToast: () => toast,
}))

vi.mock('@/stores/live-sessions', () => ({
  useLiveSessionsStore: () => store,
}))

function session(overrides: Partial<LiveSession>): LiveSession {
  return {
    id: 'k3j9x2',
    orbit_id: ORBIT,
    user_id: 'user-1',
    name: 'training run',
    relay_id: 'local',
    started_at: '2026-09-29T10:00:00Z',
    last_heartbeat_at: '2026-09-29T10:00:30Z',
    connected: true,
    ended_at: null,
    status: LiveSessionStatusEnum.live,
    ...overrides,
  }
}

function mountView() {
  return mount(OrbitFlowView, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
        },
      },
    },
  })
}

describe('OrbitFlowView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.sessionsList = []
    store.notConfigured = false
    store.loadSessions.mockResolvedValue(undefined)
  })

  it('loads the sessions of the routed orbit', async () => {
    mountView()
    await flushPromises()

    expect(store.loadSessions).toHaveBeenCalledWith(ORG, ORBIT)
  })

  it('lists sessions with name, start time and status, linking to each session', async () => {
    const live = session({ id: 'live1', name: 'training run' })
    const ended = session({
      id: 'ended1',
      name: 'eval run',
      status: LiveSessionStatusEnum.ended,
      ended_at: '2026-09-29T11:00:00Z',
    })
    store.sessionsList = [live, ended]

    const wrapper = mountView()
    await flushPromises()

    const rows = wrapper.findAll('.session')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.get('.session__name').text()).toBe('training run')
    expect(rows[0]!.get('.session__started').text()).toBe(
      new Date(live.started_at).toLocaleString(),
    )
    expect(rows[0]!.get('.status').text()).toBe('live')
    expect(rows[1]!.get('.session__name').text()).toBe('eval run')
    expect(rows[1]!.get('.status').text()).toBe('ended')
    expect(JSON.parse(rows[1]!.attributes('data-to')!)).toEqual({
      name: 'orbit-flow-session',
      params: { organizationId: ORG, id: ORBIT, sessionId: 'ended1' },
    })
    expect(wrapper.text()).not.toContain('Run Flow locally')
  })

  it('shows both sets of instructions when there are no sessions', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.session').exists()).toBe(false)
    expect(wrapper.text()).toContain('Run Flow locally')
    expect(wrapper.text()).toContain('lumlflow ui')
    expect(wrapper.text()).toContain('Expose a running service')
    expect(wrapper.text()).toContain(
      `luml-tunnel expose 5000 --name "training run" --organization ${ORG} --orbit ${ORBIT}`,
    )
  })

  it('shows a notice in place of the list when the feature is off', async () => {
    store.notConfigured = true

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-testid="not-configured"]').text()).toBe(
      'Live sessions are not set up in this deployment.',
    )
    expect(wrapper.text()).not.toContain('Run Flow locally')
    expect(wrapper.find('.session').exists()).toBe(false)
  })

  it('reports a failed load in a toast', async () => {
    store.loadSessions.mockRejectedValue(new Error('boom'))

    mountView()
    await flushPromises()

    expect(toast.add).toHaveBeenCalledTimes(1)
  })
})
