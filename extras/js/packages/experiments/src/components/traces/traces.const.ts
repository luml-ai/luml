import type { GetTracesParams } from '@/interfaces/interfaces'
import { TraceStateEnum } from '@/providers/ExperimentSnapshotApiProvider.interface'

export const TRACE_STATE_MAP = {
  [TraceStateEnum.UNSPECIFIED]: 'Unspecified',
  [TraceStateEnum.OK]: 'OK',
  [TraceStateEnum.ERROR]: 'Error',
  [TraceStateEnum.IN_PROGRESS]: 'In Progress',
} as const

export const INITIAL_REQUEST_PARAMS: GetTracesParams = {
  limit: 20,
  sort_by: 'created_at',
  order: 'desc',
  search: '',
}

export const SORTED_FIELDS = ['created_at', 'execution_time', 'span_count'] as const
