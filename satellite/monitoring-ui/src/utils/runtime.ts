import {
  Compare,
  SectionState,
  type Card,
  type RuntimeBaseline,
  type RuntimeResponse,
  type StatusBreakdownRow,
} from '@/api/monitoring/interfaces'
import type { EmptyStateContent } from '@/types/empty'

export function getOutcomeLabel(status: string): string {
  const words = status.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function getStatusRowKey(row: StatusBreakdownRow): string {
  return `${row.status}:${row.status_code ?? 'none'}`
}

export function isFailedOutcome(row: Pick<StatusBreakdownRow, 'status'>): boolean {
  return row.status !== 'success'
}

export function getRuntimeEmptyState(runtime: RuntimeResponse): EmptyStateContent | null {
  if (runtime.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Runtime data unavailable',
      detail: 'The monitoring store could not provide runtime metrics for this window.',
    }
  }
  if (runtime.state === SectionState.EMPTY || runtime.request_count === 0) {
    return {
      title: 'No calls in this window',
      detail:
        'Nothing reached the deployment in the selected range. Widen the range, or send traffic.',
    }
  }
  return null
}

const RUNTIME_CARD_FIELDS: {
  key: keyof RuntimeBaseline & keyof RuntimeResponse
  label: string
  unit: string | null
}[] = [
  { key: 'request_count', label: 'Requests', unit: null },
  { key: 'success_rate', label: 'Success rate', unit: 'ratio' },
  { key: 'error_rate', label: 'Error rate', unit: 'ratio' },
  { key: 'latency_p50_ms', label: 'Latency p50', unit: 'ms' },
  { key: 'latency_p95_ms', label: 'Latency p95', unit: 'ms' },
  { key: 'latency_max_ms', label: 'Latency max', unit: 'ms' },
  { key: 'timeout_count', label: 'Timeouts', unit: null },
  { key: 'failed_inference_count', label: 'Failed inferences', unit: null },
]

export function getRuntimeCards(runtime: RuntimeResponse, compare: Compare): Card[] {
  const baseline = compare === Compare.OFF ? null : (runtime.baseline ?? null)
  return RUNTIME_CARD_FIELDS.map(({ key, label, unit }) => {
    const value = (runtime[key] as number | null | undefined) ?? null
    const previous = baseline ? ((baseline[key] as number | null | undefined) ?? null) : null
    return {
      key,
      label,
      unit,
      value,
      delta: value != null && previous != null ? value - previous : null,
      delta_kind: baseline ? compare : null,
    }
  })
}
