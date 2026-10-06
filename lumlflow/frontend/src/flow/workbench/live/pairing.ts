import type { FlowSessionHandle } from './useFlowSession'
import { formatCost } from '../model/format'
import type { PairedAgent } from '../model/types'

export const IDLE_AFTER_MS = 90_000

export function pairedAgent(
  session: FlowSessionHandle,
  now: number = Date.now(),
): PairedAgent | undefined {
  const agent = session.agent.value
  if (agent === null) return undefined

  const branch = session.brief.value?.branch ?? ''
  const latest = [...session.transactions.value]
    .reverse()
    .find((entry) => entry.actor === agent.actor)

  const quiet = latest === undefined ? Number.NaN : now - Date.parse(latest.ts)
  if (!Number.isFinite(quiet)) return { label: agent.label, branch, state: 'idle' }

  if (quiet < IDLE_AFTER_MS) {
    return { label: agent.label, branch, state: 'working', task: latest?.intent }
  }
  return {
    label: agent.label,
    branch,
    state: 'idle',
    idleFor: formatCost(quiet / 1000),
  }
}
