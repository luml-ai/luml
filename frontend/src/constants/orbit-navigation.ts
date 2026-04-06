export const TAB_TO_ROUTE: Record<string, string> = {
  registry: 'orbit-registry',
  deployments: 'orbit-deployments',
  satellites: 'orbit-satellites',
}

export const ROUTE_TO_TAB: Record<string, string> = {
  orbit: 'registry',
  'orbit-registry': 'registry',
  'orbit-deployments': 'deployments',
  'orbit-satellites': 'satellites',
  'orbit-secrets': 'deployments',
}
