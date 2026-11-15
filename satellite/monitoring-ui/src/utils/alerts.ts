import type { AlertBanner, Severity } from '@/api/monitoring/interfaces'
import {
  ALERT_GROUP_LABELS,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  SEVERITY_TAG_SEVERITIES,
  UNKNOWN_SEVERITY_TAG_SEVERITY,
} from '@/constants/alerts'
import type { TagSeverity } from '@/types/tag'

export function getAlertTitle(alert: AlertBanner): string {
  const group = ALERT_GROUP_LABELS[alert.group] ?? alert.group.replace(/_/g, ' ')
  return `${group} ${SEVERITY_LABELS[alert.severity]}`
}

export function getAlertKey(alert: AlertBanner): string {
  return `${alert.group}:${alert.metric}:${alert.feature ?? ''}`
}

export function sortAlertsBySeverity(alerts: AlertBanner[]): AlertBanner[] {
  return [...alerts].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
}

export function getSeverityTagSeverity(severity: string): TagSeverity {
  return SEVERITY_TAG_SEVERITIES[severity as Severity] ?? UNKNOWN_SEVERITY_TAG_SEVERITY
}

export function getSeverityLabel(severity: string): string {
  return SEVERITY_LABELS[severity as Severity] ?? severity
}
