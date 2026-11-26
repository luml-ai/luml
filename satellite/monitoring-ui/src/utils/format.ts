import { Severity } from '@/api/monitoring/interfaces'

const integerFormat = new Intl.NumberFormat('en-US')
const decimalFormat = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatDecimal(value: number): string {
  return decimalFormat.format(value)
}

export function getSeverityByThresholds(
  value: number,
  warning: number,
  critical: number,
): Severity {
  if (value >= critical) return Severity.CRITICAL
  if (value >= warning) return Severity.WARNING
  return Severity.OK
}

export function formatInteger(value: number): string {
  return integerFormat.format(value)
}

export function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

export function formatPercentPoints(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}pp`
}

export function formatSignedDelta(delta: number, formatter: (value: number) => string): string {
  const arrow = delta > 0 ? '↑' : delta < 0 ? '↓' : '→'
  return `${arrow} ${formatter(Math.abs(delta))}`
}

export function getDeltaTone(delta: number): 'up' | 'down' | 'flat' {
  if (delta > 0) return 'up'
  if (delta < 0) return 'down'
  return 'flat'
}

export function formatMs(value: number): string {
  return `${Math.round(value)} ms`
}

export function formatOptional(
  value: number | null | undefined,
  formatter: (value: number) => string,
): string {
  return value == null ? '—' : formatter(value)
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
