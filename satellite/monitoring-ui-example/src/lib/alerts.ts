import type { AlertBanner } from '@/api/types'

const GROUP_LABELS: Record<string, string> = {
  runtime: 'Runtime',
  data_quality: 'Data quality',
  feature_drift: 'Feature drift',
  output_drift: 'Output drift',
  multivariate: 'Multivariate drift',
}

export function groupLabel(group: string): string {
  return GROUP_LABELS[group] ?? group.replace(/_/g, ' ')
}

/** What the alert is about: the feature when there is one, otherwise the metric itself. */
export function alertSubject(alert: AlertBanner): string {
  if (alert.feature) return alert.feature
  const [, subject] = alert.metric.split(':')
  return (subject ?? alert.metric).replace(/_/g, ' ')
}

/** "40m", "3h 10m" — how long the alert has been firing. */
export function durationLabel(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const minutes = Math.round(seconds / 60)
  if (minutes < 1) return '<1m'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}
