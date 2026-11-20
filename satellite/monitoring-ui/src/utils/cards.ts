import type { Card } from '@/api/monitoring/interfaces'
import { SEVERITY_CARD_SEVERITIES } from '@/constants/alerts'
import { CardSeverity } from '@/types/card'
import { formatInteger, formatMs, formatPercent, formatPercentPoints } from '@/utils/format'

const TABULAR_ONLY_CARDS = ['drifted_features', 'output_drift']

export function formatCardValue(card: Card): string {
  if (card.value == null) return '—'
  if (card.unit === 'ratio') return formatPercent(card.value)
  if (card.unit === 'ms') return formatMs(card.value)
  if (card.unit === 'score') return card.value.toFixed(2)
  return formatInteger(card.value)
}

export function getCompareTargetLabel(kind: Card['delta_kind']): string {
  if (kind === 'previous') return 'previous period'
  if (kind === 'custom') return 'compared period'
  return kind ?? 'reference'
}

export function formatCardDelta(card: Card): string | null {
  if (card.delta == null) return null
  const arrow = card.delta > 0 ? '↑' : card.delta < 0 ? '↓' : '→'
  return `${arrow} ${formatDeltaMagnitude(card)} vs ${getCompareTargetLabel(card.delta_kind)}`
}

function formatDeltaMagnitude(card: Card): string {
  const magnitude = Math.abs(card.delta ?? 0)
  if (card.unit === 'ratio') return formatPercentPoints(magnitude)
  if (card.unit === 'ms') return formatMs(magnitude)
  return formatInteger(magnitude)
}

export function getCardSeverity(card: Card): CardSeverity {
  if (card.key === 'active_alerts') {
    return (card.critical_count ?? 0) > 0 ? CardSeverity.DANGER : CardSeverity.DEFAULT
  }
  const serverSeverity = card.severity ? SEVERITY_CARD_SEVERITIES[card.severity] : null
  if (serverSeverity) return serverSeverity
  if (card.key === 'drifted_features' || card.key === 'timeout_count') {
    return (card.value ?? 0) > 0 ? CardSeverity.WARNING : CardSeverity.DEFAULT
  }
  return CardSeverity.DEFAULT
}

export function isCardVisibleForKind(card: Card, isTabular: boolean): boolean {
  return isTabular || !TABULAR_ONLY_CARDS.includes(card.key)
}
