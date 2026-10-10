export interface FlowCommand {
  label: string
  code: string
}

export const RELAYED_FLOWS_DOCS_URL = `${import.meta.env.VITE_DOCS_URL}/apps/lumlflow/relayed_flows`

export const LOCAL_FLOW_COMMANDS: FlowCommand[] = [
  { label: 'Install', code: 'pip install lumlflow' },
  { label: 'Run', code: 'lumlflow ui' },
]
