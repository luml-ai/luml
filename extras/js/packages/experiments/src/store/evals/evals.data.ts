import type { InitialDatasetParamsType } from './evals.interface'
import type { GetEvalsByDatasetParams } from '@/interfaces/interfaces'

export const INITIAL_PARAMS: InitialDatasetParamsType = {
  limit: 20,
  sort_by: 'created_at' as GetEvalsByDatasetParams['sort_by'],
  order: 'desc' as GetEvalsByDatasetParams['order'],
  search: '',
}
