import { Severity } from '@/api/monitoring/interfaces'

export const ALERT_GROUP_LABELS: Record<string, string> = {
  runtime: 'Runtime',
  data_quality: 'Data Quality',
  feature_drift: 'Feature Drift',
  output_drift: 'Output Drift',
  multivariate: 'Multivariate Drift',
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  [Severity.OK]: 'Ok',
  [Severity.WARNING]: 'Warning',
  [Severity.CRITICAL]: 'Critical',
}

export const SEVERITY_ORDER: Record<Severity, number> = {
  [Severity.CRITICAL]: 0,
  [Severity.WARNING]: 1,
  [Severity.OK]: 2,
}
