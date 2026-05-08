import type { InitialDatasetParamsType } from './evals.interface'

export const INITIAL_PARAMS: InitialDatasetParamsType = {
  limit: 20,
  sort_by: 'created_at',
  order: 'desc',
  search: '',
  filters: [],
}

export const COMPARISON_LIMIT = 100_000
