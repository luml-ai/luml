import {
  SectionState,
  Severity,
  type AlertBanner,
  type AlertsResponse,
} from '@/api/monitoring/interfaces'
import {
  ALERT_CHART_COLORS,
  ALERT_GROUP_LABELS,
  ALERT_GROUP_TABS,
  ALERT_STATE_ACKNOWLEDGED,
  ALERT_STATE_OPEN,
  ALERT_THRESHOLD_SOURCE_PROFILE,
  ALERT_VALUE_COLORS,
  AlertSortField,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  SEVERITY_TAG_SEVERITIES,
  UNKNOWN_SEVERITY_TAG_SEVERITY,
} from '@/constants/alerts'
import type { TagSeverity } from '@/types/tag'
import type { EmptyStateContent } from '@/types/empty'
import type { TableSortOrder } from '@/constants/traces'
import { DEFAULT_CHART_COLOR } from '@/constants/charts'
import type { TabKey } from '@/types/tabs'

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

export function getAlertGroupLabel(group: string): string {
  return ALERT_GROUP_LABELS[group] ?? group.replace(/_/g, ' ')
}

export function getAlertName(alert: AlertBanner): string {
  const name = alert.label ?? alert.metric
  return alert.feature ? `${name} · ${alert.feature}` : name
}

export function getAlertValue(alert: AlertBanner): string {
  return alert.value_label ?? (alert.current_value == null ? '—' : String(alert.current_value))
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 1) return `${Math.max(Math.round(seconds), 0)}s`
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return minutes % 60 ? `${hours}h ${minutes % 60}m` : `${hours}h`
  const days = Math.floor(hours / 24)
  return hours % 24 ? `${days}d ${hours % 24}h` : `${days}d`
}

function getAlertSortValue(alert: AlertBanner, field: AlertSortField): string | number | null {
  if (field === AlertSortField.NAME) return getAlertName(alert).toLowerCase()
  if (field === AlertSortField.SEEN) return alert.last_seen ? Date.parse(alert.last_seen) : null
  if (field === AlertSortField.TYPE) return SEVERITY_ORDER[alert.severity] ?? null
  return alert[field] ?? null
}

function compareAlerts(
  a: AlertBanner,
  b: AlertBanner,
  field: AlertSortField,
  order: TableSortOrder,
): number {
  const left = getAlertSortValue(a, field)
  const right = getAlertSortValue(b, field)
  if (left === right) return 0
  if (left === null) return 1
  if (right === null) return -1
  return (left < right ? -1 : 1) * order
}

export function getSortedAlerts(
  groups: AlertsResponse['groups'],
  field: AlertSortField | null,
  order: TableSortOrder,
): AlertBanner[] {
  return groups.flatMap(({ group, alerts }) => {
    const rows = alerts.map((alert) => ({ ...alert, group }))
    return field ? rows.sort((a, b) => compareAlerts(a, b, field, order)) : rows
  })
}

export function isAlertSortField(field: unknown): field is AlertSortField {
  return Object.values(AlertSortField).includes(field as AlertSortField)
}

export function countAlerts(groups: AlertsResponse['groups'], severity?: Severity): number {
  return groups.reduce(
    (sum, { alerts }) =>
      sum +
      (severity ? alerts.filter((alert) => alert.severity === severity).length : alerts.length),
    0,
  )
}

export function getAlertsEmptyState(response: AlertsResponse): EmptyStateContent | null {
  if (response.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Alerts unavailable',
      detail: 'The monitoring store could not provide alerts for this window.',
    }
  }
  if (response.state === SectionState.EMPTY || !countAlerts(response.groups)) {
    return {
      title: 'No open alerts',
      detail: 'All monitored metrics are within their thresholds for this window.',
    }
  }
  return null
}

export function findAlert(alerts: AlertBanner[], key: string | null): AlertBanner | null {
  if (!key) return null
  return alerts.find((alert) => getAlertKey(alert) === key) ?? null
}

export function getAlertState(alert: AlertBanner): string {
  return alert.state ?? ALERT_STATE_OPEN
}

export function isAlertAcknowledged(alert: AlertBanner): boolean {
  return alert.state === ALERT_STATE_ACKNOWLEDGED
}

export function getAlertThreshold(alert: AlertBanner): string {
  return alert.threshold_label ?? (alert.threshold == null ? '—' : String(alert.threshold))
}

export function getAlertThresholdNote(alert: AlertBanner): string {
  return alert.threshold_source === ALERT_THRESHOLD_SOURCE_PROFILE
    ? 'Threshold comes from the deployment reference profile.'
    : 'Threshold is the built-in default; the profile ships its own rules, which the metrics do not read yet.'
}

export function getAlertTargetTab(alert: AlertBanner): TabKey | null {
  return ALERT_GROUP_TABS[alert.group] ?? null
}

export function getAlertValueColor(severity: string): string | undefined {
  return ALERT_VALUE_COLORS[severity as Severity]
}

export function getAlertChartColor(severity: string): string {
  return ALERT_CHART_COLORS[severity as Severity] ?? DEFAULT_CHART_COLOR
}
