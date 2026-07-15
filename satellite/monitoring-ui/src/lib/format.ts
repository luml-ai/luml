import { Severity, type Card } from '@/api/types'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger'

export function severityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1)
}

const integerFormat = new Intl.NumberFormat('en-US')

export function formatCardValue(card: Card): string {
  if (card.value == null) return '—'
  if (card.unit === 'ratio') return `${(card.value * 100).toFixed(1)}%`
  if (card.unit === 'ms') return `${Math.round(card.value)} ms`
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
  return `${arrow} ${formatDelta(card)} vs ${card.delta_kind ?? 'reference'}`
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
  return 'neutral'
}

/** A 0..1 rate as a percentage, or an em dash when the metric was not computed. */
export function formatRate(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
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
