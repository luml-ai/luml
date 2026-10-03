import type { FlowCommand } from './FlowCommandCard.vue'

export const RELAYED_FLOWS_DOCS_URL = `${import.meta.env.VITE_DOCS_URL}/apps/lumlflow/relayed_flows`

export const RUN_LOCALLY_HINTS = [
  'Flow is a local live tracker for ML experiments.',
  'Log parameters, metrics, and artifacts as they stream in.',
  'Compare them side by side in a browser UI.',
]

export const RUN_LOCALLY_COMMANDS: FlowCommand[] = [
  { label: 'Install', code: 'pip install lumlflow' },
  { label: 'Run', code: 'lumlflow ui' },
]
