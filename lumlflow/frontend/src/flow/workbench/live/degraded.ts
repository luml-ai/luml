/**
 * What is wrong, said as a state rather than as a spinner.
 *
 * Every degraded condition the spec names has a surface, because a failure mode
 * without one is a spinner that never resolves. This is the derivation that
 * picks them, kept pure so the conditions can be asserted without a socket.
 *
 * Two distinctions do the work here. **The daemon being down is not the socket
 * dropping**: a dropped socket reconnects and replays, and the workbench keeps
 * working meanwhile; a daemon that is gone can receive nothing, and the surface
 * has to say so and offer the command that starts one. Only an RPC round-trip
 * separates them, which is why `reachable` is a recorded fact here and not a
 * guess from the socket's state. **Unpaired is not idle**: an unpaired
 * workbench is a first-class working state, and calling it idle would read as
 * an agent that went quiet.
 */

import type { FlowState } from '../model/types'

export type DegradedKind =
  | 'daemon-down'
  | 'socket-dropped'
  | 'socket-refused'
  | 'kernel-not-started'
  | 'behind-cursor'

export interface SessionFacts {
  /** The last RPC round-trip answered. False is the daemon-down state. */
  reachable: boolean
  /** How the journal socket stands. */
  stream: 'connecting' | 'open' | 'dropped' | 'refused' | 'closed'
  kernel: 'running' | 'stopped'
  /** Runs in flight on this flow. */
  running: number
  /** An agent session is registered — detected from the journal, never declared. */
  paired: boolean
  /** Transactions committed since this client was last here. */
  changesBehind: number
}

/**
 * Everything true right now, most severe first. More than one can be, and each
 * gets its own surface — a daemon that is down while the user is also twelve
 * transactions behind is both of those things.
 */
export function degradedStates(facts: SessionFacts): DegradedKind[] {
  const states: DegradedKind[] = []
  if (!facts.reachable) states.push('daemon-down')
  // Subsumed while the daemon is down: the socket dropping is how that
  // announces itself, and two banners for one cause is one banner too many.
  else if (facts.stream === 'refused') states.push('socket-refused')
  else if (facts.stream === 'dropped') states.push('socket-dropped')
  if (facts.reachable && facts.kernel === 'stopped') states.push('kernel-not-started')
  if (facts.changesBehind > 0) states.push('behind-cursor')
  return states
}

/**
 * The five-valued flow indicator.
 *
 * Ordered by what a reader most needs: a workbench nobody is serving, then
 * work in flight, then the kernel that has not started, then the pairing state.
 * `idle` is the last one left — paired, and nothing running.
 */
export function flowState(facts: SessionFacts): FlowState {
  if (!facts.reachable) return 'daemon-down'
  if (facts.running > 0) return 'running'
  if (facts.kernel === 'stopped') return 'kernel-not-started'
  if (!facts.paired) return 'unpaired'
  return 'idle'
}
