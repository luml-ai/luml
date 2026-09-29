import { enableAutoUnmount, mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import OrbitFlowSessionView from '../OrbitFlowSessionView.vue'
import { LiveSessionStatusEnum, type LiveSession } from '@/lib/api/live-sessions/interfaces'
import { LIVE_SESSION_ACCESS_NEEDED_MESSAGE } from '@/stores/live-sessions'

const ORG = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT = '0199c8cf-4d35-783b-9f81-cb3cec788074'
const SESSION = 'k3f9x2ab'
const RELAY_ORIGIN = 'http://k3f9x2ab.tunnel.example'

const liveSessionsApi = vi.hoisted(() => ({
  getItem: vi.fn(),
  issueViewToken: vi.fn(),
  end: vi.fn(),
}))

const toast = { add: vi.fn() }

vi.mock('@/lib/api', () => ({ api: { liveSessions: liveSessionsApi } }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: ORG, id: ORBIT, sessionId: SESSION } }),
}))

vi.mock('primevue', () => ({
  Button: {
    props: ['label'],
    emits: ['click'],
    template: '<button @click="$emit(\'click\')">{{ label }}</button>',
  },
  useToast: () => toast,
}))

function session(overrides: Partial<LiveSession> = {}): LiveSession {
  return {
    id: SESSION,
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

let tokenCount = 0

function nextViewToken() {
  tokenCount += 1
  const token = `view-token-${tokenCount}`
  return {
    token,
    launch_url: `${RELAY_ORIGIN}/.luml-tunnel/launch?token=${token}`,
    expires_at: '2026-09-29T10:05:00Z',
  }
}

function mountView() {
  return mount(OrbitFlowSessionView, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a><slot /></a>' },
        UiPageLoader: { template: '<div data-testid="loader" />' },
      },
    },
  })
}

function postFromRelay(data: unknown, origin = RELAY_ORIGIN) {
  window.dispatchEvent(new MessageEvent('message', { data, origin }))
}

enableAutoUnmount(afterEach)

const accessNeeded = { type: LIVE_SESSION_ACCESS_NEEDED_MESSAGE, session: SESSION }

describe('OrbitFlowSessionView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-29T10:01:00Z'))
    tokenCount = 0
    liveSessionsApi.getItem.mockResolvedValue(session())
    liveSessionsApi.issueViewToken.mockImplementation(async () => nextViewToken())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows a live session in a frame that loads the launch address of a new view token', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(liveSessionsApi.getItem).toHaveBeenCalledWith(ORG, ORBIT, SESSION)
    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledWith(ORG, ORBIT, SESSION)
    const frame = wrapper.get('[data-testid="session-frame"]')
    expect(frame.attributes('src')).toBe(`${RELAY_ORIGIN}/.luml-tunnel/launch?token=view-token-1`)
    expect(frame.attributes()).toHaveProperty('credentialless')
    expect(wrapper.find('[data-testid="open-in-new-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stop-session"]').exists()).toBe(true)
    expect(wrapper.get('h1').text()).toBe('training run')
  })

  it('opens the session in a new tab with a view token of its own', async () => {
    const tab = { opener: {}, location: { href: '' }, close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-testid="open-in-new-tab"]').trigger('click')
    await flushPromises()

    expect(open).toHaveBeenCalledWith('', '_blank')
    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledTimes(2)
    expect(tab.opener).toBeNull()
    expect(tab.location.href).toBe(`${RELAY_ORIGIN}/.luml-tunnel/launch?token=view-token-2`)
    expect(wrapper.get('[data-testid="session-frame"]').attributes('src')).toContain('view-token-1')
    open.mockRestore()
  })

  it('closes the new tab when no view token can be issued', async () => {
    const tab = { opener: {}, location: { href: '' }, close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    const wrapper = mountView()
    await flushPromises()
    liveSessionsApi.issueViewToken.mockRejectedValueOnce(new Error('ended'))

    await wrapper.get('[data-testid="open-in-new-tab"]').trigger('click')
    await flushPromises()

    expect(tab.close).toHaveBeenCalled()
    expect(tab.location.href).toBe('')
    expect(toast.add).toHaveBeenCalledTimes(1)
    open.mockRestore()
  })

  it('stops the session, removes the frame and shows the notice for an ended session', async () => {
    liveSessionsApi.end.mockResolvedValue(
      session({ status: LiveSessionStatusEnum.ended, ended_at: '2026-09-29T10:01:00Z' }),
    )
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-testid="stop-session"]').trigger('click')
    await flushPromises()

    expect(liveSessionsApi.end).toHaveBeenCalledWith(ORG, ORBIT, SESSION)
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="session-ended"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stop-session"]').exists()).toBe(false)
  })

  it('shows the time of the last heartbeat for a disconnected session, without a frame', async () => {
    const lastHeartbeat = '2026-09-29T09:58:00Z'
    liveSessionsApi.getItem.mockResolvedValue(
      session({ status: LiveSessionStatusEnum.disconnected, last_heartbeat_at: lastHeartbeat }),
    )
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-testid="session-disconnected"]').text()).toContain(
      new Date(lastHeartbeat).toLocaleString(),
    )
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
    expect(liveSessionsApi.issueViewToken).not.toHaveBeenCalled()
  })

  it('shows a notice for an ended session, without a frame', async () => {
    liveSessionsApi.getItem.mockResolvedValue(
      session({ status: LiveSessionStatusEnum.ended, ended_at: '2026-09-29T09:00:00Z' }),
    )
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="session-ended"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="open-in-new-tab"]').exists()).toBe(false)
    expect(liveSessionsApi.issueViewToken).not.toHaveBeenCalled()
  })

  it('launches again when the relay page reports missing access after the cookie ended', async () => {
    const wrapper = mountView()
    await flushPromises()
    vi.setSystemTime(new Date('2026-09-29T10:31:00Z'))

    postFromRelay(accessNeeded)
    await flushPromises()

    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="session-frame"]').attributes('src')).toContain('view-token-2')
  })

  it('offers a new tab instead of launching again when the frame does not keep the cookie', async () => {
    const wrapper = mountView()
    await flushPromises()

    postFromRelay(accessNeeded)
    await flushPromises()

    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="frame-blocked"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="frame-blocked-open"]').exists()).toBe(true)
  })

  it('ignores messages from other origins, of other types or for other sessions', async () => {
    const wrapper = mountView()
    await flushPromises()
    vi.setSystemTime(new Date('2026-09-29T10:31:00Z'))

    postFromRelay(accessNeeded, 'https://evil.example')
    postFromRelay({ type: 'something-else', session: SESSION })
    postFromRelay({ type: LIVE_SESSION_ACCESS_NEEDED_MESSAGE, session: 'other123' })
    await flushPromises()

    expect(liveSessionsApi.issueViewToken).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="session-frame"]').attributes('src')).toContain('view-token-1')
  })

  it('shows a notice when live sessions are not set up in this deployment', async () => {
    liveSessionsApi.getItem.mockRejectedValue({ response: { status: 501 } })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="not-configured"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
    expect(toast.add).not.toHaveBeenCalled()
  })

  it('reports a failed load in a toast', async () => {
    liveSessionsApi.getItem.mockRejectedValue(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()

    expect(toast.add).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="session-frame"]').exists()).toBe(false)
  })
})
