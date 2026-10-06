import type { FlowState } from '../model/types'

export type DegradedKind =
  | 'daemon-down'
  | 'socket-dropped'
  | 'socket-refused'
  | 'kernel-not-started'
  | 'behind-cursor'

export interface SessionFacts {
  reachable: boolean
  stream: 'connecting' | 'open' | 'dropped' | 'refused' | 'closed'
  kernel: 'running' | 'stopped'
  running: number
  paired: boolean
  changesBehind: number
}

export function degradedStates(facts: SessionFacts): DegradedKind[] {
  const states: DegradedKind[] = []
  if (!facts.reachable) states.push('daemon-down')
  else if (facts.stream === 'refused') states.push('socket-refused')
  else if (facts.stream === 'dropped') states.push('socket-dropped')
  if (facts.reachable && facts.kernel === 'stopped') states.push('kernel-not-started')
  if (facts.changesBehind > 0) states.push('behind-cursor')
  return states
}

export function flowState(facts: SessionFacts): FlowState {
  if (!facts.reachable) return 'daemon-down'
  if (facts.running > 0) return 'running'
  if (facts.kernel === 'stopped') return 'kernel-not-started'
  if (!facts.paired) return 'unpaired'
  return 'idle'
}
