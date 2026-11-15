import {
  SectionState,
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
