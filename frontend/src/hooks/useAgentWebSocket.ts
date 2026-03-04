import { watch, onUnmounted, ref } from 'vue'
import { useDataAgentStore } from '@/stores/data-agent'
import { api } from '@/lib/api'

const MAX_RECONNECT_ATTEMPTS = 20
const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 10000

export function useAgentWebSocket() {
  const store = useDataAgentStore()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let activeRunId: string | null = null
  let intentionalClose = false
  const connected = ref(false)
  const reconnecting = ref(false)

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function disconnect() {
    intentionalClose = true
    clearReconnectTimer()
    reconnecting.value = false
    reconnectAttempts = 0
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  function scheduleReconnect(runId: string) {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      reconnecting.value = false
      return
    }
    reconnecting.value = true
    const delay = Math.min(BASE_DELAY_MS * Math.pow(2, reconnectAttempts), MAX_DELAY_MS)
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (activeRunId === runId) {
        connect(runId)
      }
    }, delay)
  }

  function connect(runId: string) {
    if (ws) {
      ws.close()
      ws = null
    }
    intentionalClose = false
    activeRunId = runId

    ws = api.dataAgent.createRunWebSocket(runId)

    ws.onopen = () => {
      connected.value = true
      reconnecting.value = false
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'snapshot') {
          store.applySnapshot(msg.data)
        } else if (msg.type === 'event') {
          store.applyEvent(msg.data)
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      if (!intentionalClose && activeRunId === runId) {
        catchUp(runId)
        scheduleReconnect(runId)
      }
    }
  }

  async function catchUp(runId: string) {
    try {
      const events = await api.dataAgent.getRunEvents(runId, store.lastSeq)
      for (const event of events) {
        store.applyEvent(event)
      }
    } catch {
      // ignore catchup errors
    }
  }

  watch(
    () => store.selectedRunId,
    (runId) => {
      if (runId != null) {
        reconnectAttempts = 0
        connect(runId)
      } else {
        disconnect()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    disconnect()
  })

  return { connected, reconnecting }
}
