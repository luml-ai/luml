import type { FlowCommand } from './FlowCommandCard.vue'

export const RUN_LOCALLY_HINTS = [
  'Flow is a local live tracker for ML experiments.',
  'Log parameters, metrics, and artifacts as they stream in.',
  'Compare them side by side in a browser UI.',
]

export const RUN_LOCALLY_COMMANDS: FlowCommand[] = [
  { label: 'Install', code: 'pip install lumlflow' },
  { label: 'Run', code: 'lumlflow ui' },
]

export const EXPOSE_HINTS = [
  'Reach a service running on another machine, such as lumlflow next to a training job.',
  'The session appears here while the agent stays connected.',
]

export function exposeCommands(organizationId: string, orbitId: string): FlowCommand[] {
  return [
    { label: 'Install', code: 'pip install "luml-tunnel[luml]"' },
    { label: 'Key', code: 'export LUML_API_KEY=<your API key>' },
    {
      label: 'Expose',
      code: `luml-tunnel expose 5000 --name "training run" --organization ${organizationId} --orbit ${orbitId}`,
    },
  ]
}
