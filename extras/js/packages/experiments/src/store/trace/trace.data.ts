import type { GetTracesParams } from '@experiments/interfaces/interfaces'

export const INITIAL_REQUEST_PARAMS: GetTracesParams = {
  limit: 20,
  sort_by: 'created_at',
  order: 'desc',
  search: '',
  filters: [],
}
