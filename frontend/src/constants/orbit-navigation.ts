export const TAB_TO_ROUTE: Record<string, string> = {
  registry: 'orbit-collections',
  deployments: 'orbit-deployments',
  satellites: 'orbit-satellites',
  flow: 'orbit-flow',
}

export const ROUTE_TO_TAB: Record<string, string> = {
  orbit: 'registry',
  'orbit-collections': 'registry',
  'orbit-deployments': 'deployments',
  'orbit-satellites': 'satellites',
  'orbit-secrets': 'deployments',
  'orbit-flow': 'flow',
}

export const ORBIT_TAB_ROUTES = [
  'orbit-collections',
  'orbit-tracks',
  'orbit-deployments',
  'orbit-satellites',
  'orbit-secrets',
  'orbit-flow',
]

export const RESOURCE_ROUTE_TO_TAB_ROUTE: Record<string, string> = {
  track: 'orbit-tracks',
  collection: 'orbit-collections',
  artifact: 'orbit-collections',
  dataset: 'orbit-collections',
  'artifact-card': 'orbit-collections',
  'experiment-snapshot': 'orbit-collections',
  attachments: 'orbit-collections',
  lineage: 'orbit-collections',
  compare: 'orbit-collections',
  'deployment-schema': 'orbit-deployments',
  'deployment-monitoring': 'orbit-deployments',
}
