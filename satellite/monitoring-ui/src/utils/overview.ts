import { SectionState, type OverviewResponse } from '@/api/monitoring/interfaces'
import type { EmptyStateContent } from '@/types/empty'

export function getOverviewEmptyState(overview: OverviewResponse): EmptyStateContent | null {
  if (overview.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Overview data unavailable',
      detail: 'The monitoring store could not provide overview metrics for this window.',
    }
  }
  if (overview.state === SectionState.EMPTY) {
    return {
      title: 'No activity in this window',
      detail: 'The worker has not produced runtime or drift results for this window yet.',
    }
  }
  return null
}
