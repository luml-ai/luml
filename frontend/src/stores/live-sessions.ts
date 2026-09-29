import { api } from '@/lib/api'
import type { LiveSession } from '@/lib/api/live-sessions/interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'

// The backend answers every live session operation with 501 when the deployment has no relay.
const NOT_CONFIGURED_STATUS = 501

export function isLiveSessionsNotConfigured(error: unknown): boolean {
  if (typeof error !== 'object' || error === null || !('response' in error)) return false
  const response = (error as { response?: { status?: unknown } }).response
  return response?.status === NOT_CONFIGURED_STATUS
}

export const useLiveSessionsStore = defineStore('live-sessions', () => {
  const sessionsList = ref<LiveSession[]>([])
  const notConfigured = ref(false)

  async function loadSessions(organizationId: string, orbitId: string) {
    try {
      sessionsList.value = await api.liveSessions.getList(organizationId, orbitId)
      notConfigured.value = false
    } catch (error) {
      sessionsList.value = []
      if (!isLiveSessionsNotConfigured(error)) throw error
      notConfigured.value = true
    }
  }

  return {
    sessionsList,
    notConfigured,
    loadSessions,
  }
})
