export interface PaginatedResponse<T> {
  items: T[]
  cursor: string | null
}

export interface GetGroupsParams {
  limit: number
  cursor: string | null
  sort_by: 'name' | 'created_at' | 'description'
  order: 'asc' | 'desc'
  search: string | null
}

export interface GetExperimentsParams {
  group_id: string
  limit: number
  cursor: string | null
  search: string | null
}

export interface GetExperimentTracesParams {
  limit: number
  cursor: string | null
}

export interface UpdateModelPayload {
  name: string | null
  tags: string[] | null
}
