import type { GetTracesParams } from '@/interfaces/interfaces'

export const INITIAL_REQUEST_PARAMS: GetTracesParams = {
  limit: 20,
  sort_by: 'created_at',
  order: 'desc',
  search: '',
}
