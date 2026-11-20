export enum TabKey {
  OVERVIEW = 'overview',
  RUNTIME = 'runtime',
  TRACES = 'traces',
  DATA_QUALITY = 'data-quality',
  FEATURE_DRIFT = 'feature-drift',
  OUTPUT_DRIFT = 'output-drift',
  REFERENCE_PROFILE = 'reference-profile',
  ALERTS = 'alerts',
}

export interface TabItem {
  key: TabKey
  label: string
}
