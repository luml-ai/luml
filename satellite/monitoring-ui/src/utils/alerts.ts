import type { AlertBanner } from '@/api/monitoring/interfaces'
import { ALERT_GROUP_LABELS, SEVERITY_LABELS, SEVERITY_ORDER } from '@/constants/alerts'

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
