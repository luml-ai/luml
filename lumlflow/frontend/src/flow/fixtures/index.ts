import type { FlowSession } from '../types'
import { churnSession } from './churn'
import { llmEvalSession } from './llm-eval'
import { largeSession } from './large'
import './events' // attaches the adversarial transaction log to churnSession

export { churnSession, llmEvalSession, largeSession }
export { churnTransactions, lastStep } from './events'
export { churnVersions } from './churn'

export interface FixtureEntry {
  id: string
  label: string
  description: string
  session: FlowSession
}

export const fixtures: FixtureEntry[] = [
  {
    id: 'churn',
    label: 'Churn · walkthrough',
    description:
      '11 assets, 7 branches. Contains a rename, a failed materialization, a structural rewire, and divergent pins across the sweep branches.',
    session: churnSession,
  },
  {
    id: 'llm-eval',
    label: 'LLM eval · walkthrough',
    description:
      '4 assets, 3 branches. Non-deterministic eval asset; traces live inside the EvalBundle rather than as assets.',
    session: llmEvalSession,
  },
  {
    id: 'large',
    label: 'Events bake-off · stress',
    description:
      '~150 assets, 20 branches, divergence mid-graph. The size at which a naive per-branch render stops working.',
    session: largeSession,
  },
]

export function fixtureById(id: string): FlowSession {
  return (fixtures.find((entry) => entry.id === id) ?? fixtures[0]).session
}
