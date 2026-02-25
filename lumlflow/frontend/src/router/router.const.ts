export const ROUTE_NAMES = {
  HOME: 'home',
  EXPERIMENT: 'experiment',
  EXPERIMENT_DETAILS: 'experiment-details',
  EXPERIMENT_OVERVIEW: 'experiment-overview',
  EXPERIMENT_METRICS: 'experiment-metrics',
  EXPERIMENT_TRACES: 'experiment-traces',
  EXPERIMENT_EVALS: 'experiment-evals',
  EXPERIMENT_ATTACHMENTS: 'experiment-attachments',
}

export const ROUTES = {
  [ROUTE_NAMES.HOME]: '/',
  [ROUTE_NAMES.EXPERIMENT]: 'experiments/:groupId',

  [ROUTE_NAMES.EXPERIMENT_DETAILS]: 'experiments/:groupId/:experimentId',
  [ROUTE_NAMES.EXPERIMENT_OVERVIEW]: '',
  [ROUTE_NAMES.EXPERIMENT_METRICS]: 'metrics',
  [ROUTE_NAMES.EXPERIMENT_TRACES]: 'traces',
  [ROUTE_NAMES.EXPERIMENT_EVALS]: 'evals',
  [ROUTE_NAMES.EXPERIMENT_ATTACHMENTS]: 'attachments',
}
