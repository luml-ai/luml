import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLiveSessionsStore } from '@/stores/live-sessions'
import { api } from '@/lib/api'
import { LiveSessionStatusEnum, type LiveSession } from '@/lib/api/live-sessions/interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    liveSessions: {
      getList: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api, true)

const ORG = 'org-1'
const ORBIT = 'orbit-1'

const SESSION: LiveSession = {
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
}

function httpError(status: number) {
  return Object.assign(new Error(`status ${status}`), { response: { status } })
}

describe('live sessions store', () => {
  let store: ReturnType<typeof useLiveSessionsStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useLiveSessionsStore()
    vi.clearAllMocks()
  })

  it('loads the sessions of the orbit', async () => {
    mockApi.liveSessions.getList.mockResolvedValue([SESSION])

    await store.loadSessions(ORG, ORBIT)

    expect(mockApi.liveSessions.getList).toHaveBeenCalledWith(ORG, ORBIT)
    expect(store.sessionsList).toEqual([SESSION])
    expect(store.notConfigured).toBe(false)
  })

  it('marks the feature as not set up when the backend answers 501', async () => {
    store.sessionsList = [SESSION]
    mockApi.liveSessions.getList.mockRejectedValue(httpError(501))

    await store.loadSessions(ORG, ORBIT)

    expect(store.notConfigured).toBe(true)
    expect(store.sessionsList).toEqual([])
  })

  it('rethrows other failures without marking the feature as off', async () => {
    mockApi.liveSessions.getList.mockRejectedValue(httpError(500))

    await expect(store.loadSessions(ORG, ORBIT)).rejects.toThrow('status 500')
    expect(store.notConfigured).toBe(false)
  })

  it('clears the notice once the feature answers again', async () => {
    mockApi.liveSessions.getList.mockRejectedValueOnce(httpError(501))
    await store.loadSessions(ORG, ORBIT)
    mockApi.liveSessions.getList.mockResolvedValueOnce([SESSION])

    await store.loadSessions(ORG, ORBIT)

    expect(store.notConfigured).toBe(false)
    expect(store.sessionsList).toEqual([SESSION])
  })
})
