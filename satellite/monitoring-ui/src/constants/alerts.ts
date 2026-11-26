import { Severity } from '@/api/monitoring/interfaces'
import { TabKey } from '@/types/tabs'
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
  SEEN = 'state',
  VALUE = 'current_value',
  TYPE = 'severity',
  DURATION = 'duration_seconds',
}

export const ALERT_STATE_ACKNOWLEDGED = 'acknowledged'

export const ALERT_STATE_OPEN = 'open'

export const ALERT_THRESHOLD_SOURCE_PROFILE = 'profile'

export const ALERT_GROUP_TABS: Record<string, TabKey> = {
  runtime: TabKey.RUNTIME,
  data_quality: TabKey.DATA_QUALITY,
  feature_drift: TabKey.FEATURE_DRIFT,
  output_drift: TabKey.OUTPUT_DRIFT,
  multivariate: TabKey.FEATURE_DRIFT,
}

export const ALERT_VALUE_COLORS: Record<Severity, string> = {
  [Severity.OK]: 'var(--p-badge-success-background)',
  [Severity.WARNING]: 'var(--p-badge-warn-background)',
  [Severity.CRITICAL]: 'var(--p-badge-danger-background)',
}

export const ALERT_CHART_COLORS: Record<Severity, string> = {
  [Severity.OK]: '--p-primary-color',
  [Severity.WARNING]: '--p-orange-500',
  [Severity.CRITICAL]: '--p-red-500',
}

export const ALERT_DIALOG_GAP = 15
