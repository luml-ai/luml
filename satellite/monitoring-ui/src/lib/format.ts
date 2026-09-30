import { Severity, type Card } from '@/api/types'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger'

export function severityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1)
}

const integerFormat = new Intl.NumberFormat('en-US')
const chartNumberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 })
const compactChartNumberFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 3,
})

export function formatChartNumber(
  value: number | null | undefined,
  { percent = false, compact = false }: { percent?: boolean; compact?: boolean } = {},
): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const scaled = percent ? value * 100 : value
  const formatter =
    compact && Math.abs(scaled) >= 10000 ? compactChartNumberFormat : chartNumberFormat
  const text = formatter.format(scaled)
  return `${text === '-0' ? '0' : text}${percent ? '%' : ''}`
}

export function formatCardValue(card: Card): string {
  if (card.value == null) return '—'
  if (card.unit === 'ratio') return `${(card.value * 100).toFixed(1)}%`
  if (card.unit === 'ms') return `${Math.round(card.value)} ms`
  if (card.unit === 'score') return card.value.toFixed(2)
  return integerFormat.format(card.value)
}

/** The muted line under a card value: a compare-delta or a key-specific detail. */
export function cardDetail(card: Card): string | null {
  if (card.key === 'active_alerts') {
    return `${card.critical_count ?? 0} critical`
  }
  if (card.key === 'drifted_features') {
    return card.feature_names?.length ? card.feature_names.join(', ') : 'none'
  }
  if (card.delta == null) return null
  const arrow = card.delta > 0 ? '↑' : card.delta < 0 ? '↓' : '→'
  const against =
    card.delta_kind === 'previous'
      ? 'previous period'
      : card.delta_kind === 'custom'
        ? 'compared period'
        : (card.delta_kind ?? 'reference')
  return `${arrow} ${formatDelta(card)} vs ${against}`
}

function formatDelta(card: Card): string {
  const magnitude = Math.abs(card.delta ?? 0)
  if (card.unit === 'ratio') return `${(magnitude * 100).toFixed(1)}pp`
  if (card.unit === 'ms') return `${Math.round(magnitude)} ms`
  return integerFormat.format(magnitude)
}

export function cardTone(card: Card): Tone {
  if (card.key === 'active_alerts') return (card.critical_count ?? 0) > 0 ? 'danger' : 'neutral'
  if (card.key === 'drifted_features') return (card.value ?? 0) > 0 ? 'warning' : 'neutral'
  // Any timeout is alert-worthy; the card must not look like an ordinary counter.
  if (card.key === 'timeout_count') return (card.value ?? 0) > 0 ? 'warning' : 'neutral'
  // A scored card carries its own severity from the worker.
  if (card.severity === Severity.CRITICAL) return 'danger'
  if (card.severity === Severity.WARNING) return 'warning'
  return 'neutral'
}

/** A 0..1 rate as a percentage, or an em dash when the metric was not computed. */
export function formatRate(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

/** A plain count with thousands separators, or an em dash when there is none. */
export function formatCount(value: number | null | undefined): string {
  if (value == null) return '—'
  return integerFormat.format(value)
}

export function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
