import { Severity } from '@/api/monitoring/interfaces'
import { CardSeverity } from '@/types/card'
import type { TagSeverity } from '@/types/tag'

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

export const UNKNOWN_SEVERITY_ORDER = Object.keys(SEVERITY_ORDER).length

export const SEVERITY_TAG_SEVERITIES: Record<Severity, TagSeverity> = {
  [Severity.OK]: 'success',
  [Severity.WARNING]: 'warn',
  [Severity.CRITICAL]: 'danger',
}

export const UNKNOWN_SEVERITY_TAG_SEVERITY: TagSeverity = 'secondary'

export const SEVERITY_COLORS: Record<Severity, string> = {
  [Severity.OK]: '{primary.color}',
  [Severity.WARNING]: '{orange.500}',
  [Severity.CRITICAL]: '{red.500}',
}

export const SEVERITY_CARD_SEVERITIES: Record<Severity, CardSeverity | null> = {
  [Severity.OK]: null,
  [Severity.WARNING]: CardSeverity.WARNING,
  [Severity.CRITICAL]: CardSeverity.DANGER,
}

export const ALERTS_COLUMN_WIDTHS = {
  name: 260,
  seen: 170,
  value: 140,
  type: 140,
  duration: 120,
}

export enum AlertSortField {
  NAME = 'name',
  SEEN = 'last_seen',
  VALUE = 'current_value',
  TYPE = 'severity',
  DURATION = 'duration_seconds',
}
