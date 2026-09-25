/**
 * Who is paired, read off the journal rather than declared.
 *
 * The session already holds the registration — `agent_begin` names an actor,
 * `agent_end` clears it — so pairing is a projection of that fact into what the
 * panel renders, and there is nothing for the user to confirm anywhere. Not
 * paired is not a failure either: a human editing cells is a supported actor,
 * so absence returns `undefined` and the panel shows the command instead.
 *
 * The two claims this makes beyond the registration are both bounded. The
 * branch is the flow's checked-out lane, and "working" means the agent has
 * committed something recently; past the threshold it reads idle with the
 * time since, which is the honest thing to say about a quiet process we do not
 * own.
 */

import type { FlowSessionHandle } from './useFlowSession'
import { formatCost } from '../model/format'
import type { PairedAgent } from '../model/types'

/** Quiet this long and the line says idle rather than claiming work. */
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

  // Registered, but nothing of theirs in view — evicted past the kept window,
  // or a timestamp that will not parse. Idle without a duration is the whole
  // truth then: "working" would be the fabricated status, and it would arrive
  // as a transition *backwards* out of idle once the eviction happened.
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
