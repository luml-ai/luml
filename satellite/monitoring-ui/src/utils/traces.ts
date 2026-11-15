import {
  SectionState,
  type SortOrder,
  type TraceRow,
  type TraceSortKey,
  type TracesResponse,
} from '@/api/monitoring/interfaces'
import type { EmptyStateContent } from '@/types/empty'
import {
  DEFAULT_TRACES_SORT_FIELD,
  DEFAULT_TRACES_SORT_ORDER,
  TRACES_COLUMN_WIDTHS,
  type TableSortOrder,
  type TracesColumn,
} from '@/constants/traces'
import { isFailedOutcome } from '@/utils/runtime'

export function getTraceStatusSeverity(row: TraceRow): 'success' | 'warn' | 'danger' {
  if (!isFailedOutcome(row)) return 'success'
  if (row.status_code >= 400 && row.status_code < 500) return 'warn'
  return 'danger'
}

export function toTraceSortKey(field: string): TraceSortKey {
  if (field === 'latency_ms') return 'latency'
  if (field === 'status') return 'status'
  return 'ts'
}

export function toSortOrder(order: TableSortOrder): SortOrder {
  return order === 1 ? 'asc' : 'desc'
}

export function normalizeTraceSort(
  field: unknown,
  order: number | null | undefined,
): { field: string; order: TableSortOrder } {
  if (typeof field !== 'string' || !field || (order !== 1 && order !== -1)) {
    return { field: DEFAULT_TRACES_SORT_FIELD, order: DEFAULT_TRACES_SORT_ORDER }
  }
  return { field, order }
}

export function getTracesEmptyState(traces: TracesResponse): EmptyStateContent | null {
  if (traces.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Traces unavailable',
      detail: 'The monitoring store could not provide inference calls for this window.',
    }
  }
  if (traces.state === SectionState.EMPTY || traces.total === 0) {
    return {
      title: 'No inference calls in this window',
      detail: 'Recent prediction requests will appear here once the deployment serves traffic.',
    }
  }
  return null
}

export function getTracesTableMinWidth(): number {
  return Object.values(TRACES_COLUMN_WIDTHS).reduce((sum, width) => sum + width, 0)
}

export function getTracesColumnStyle(column: TracesColumn) {
  return { width: `${TRACES_COLUMN_WIDTHS[column]}px` }
}

export function clampTracesOffset(offset: number, total: number | null): number {
  return total !== null && offset >= total ? 0 : offset
}
