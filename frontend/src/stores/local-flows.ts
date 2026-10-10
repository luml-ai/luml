import type { LocalFlow } from '@/utils/services/LocalStorageService.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { defineStore } from 'pinia'
import { ref } from 'vue'

const REACHABILITY_TIMEOUT_MS = 3000

// Flow answers this path without a key and allows every origin.
const LUMLFLOW_STATUS_PATH = '/api/auth/status'

export function localFlowUrl(flow: Pick<LocalFlow, 'address' | 'port'>) {
  return `http://${flow.address}:${flow.port}`
}

export function localFlowKey(flow: Pick<LocalFlow, 'address' | 'port'>) {
  return `${flow.address}:${flow.port}`
}

export function localFlowExistsMessage(existing: LocalFlow) {
  return `${localFlowKey(existing)} is already added as "${existing.name}".`
}

export async function isLocalFlowReachable(flow: Pick<LocalFlow, 'address' | 'port'>) {
  try {
    const response = await fetch(`${localFlowUrl(flow)}${LUMLFLOW_STATUS_PATH}`, {
      signal: AbortSignal.timeout(REACHABILITY_TIMEOUT_MS),
    })
    return response.ok
  } catch {
    return false
  }
}

function isLocalFlow(value: unknown): value is LocalFlow {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  return (
    typeof entry.name === 'string' &&
    typeof entry.address === 'string' &&
    typeof entry.port === 'number'
  )
}

function readStoredFlows(): LocalFlow[] {
  const stored: unknown = LocalStorageService.get('localFlows')
  return Array.isArray(stored) ? stored.filter(isLocalFlow) : []
}

// Local flows belong to the browser, not to an orbit or a user: every Flow page shows them.
export const useLocalFlowsStore = defineStore('local-flows', () => {
  const localFlows = ref<LocalFlow[]>(readStoredFlows())

  function findLocalFlow(flow: Pick<LocalFlow, 'address' | 'port'>) {
    return localFlows.value.find((entry) => localFlowKey(entry) === localFlowKey(flow))
  }

  function addLocalFlow(flow: LocalFlow) {
    const existing = findLocalFlow(flow)
    if (existing) {
      throw new Error(localFlowExistsMessage(existing))
    }
    localFlows.value = [...localFlows.value, flow]
    LocalStorageService.set('localFlows', localFlows.value)
  }

  function removeLocalFlow(flow: Pick<LocalFlow, 'address' | 'port'>) {
    localFlows.value = localFlows.value.filter(
      (entry) => localFlowKey(entry) !== localFlowKey(flow),
    )
    LocalStorageService.set('localFlows', localFlows.value)
  }

  return {
    localFlows,
    findLocalFlow,
    addLocalFlow,
    removeLocalFlow,
  }
})
