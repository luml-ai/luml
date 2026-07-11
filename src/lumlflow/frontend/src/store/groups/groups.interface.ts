export interface Group {
  id: string
  name: string
  description: string | null
  created_at: string
  tags: string[] | null
  last_modified: string | null
}

export type UpdateGroupPayload = Pick<Group, 'name' | 'description' | 'tags'>

export interface DetailedGroup extends Group {
  experiments_static_params: string[]
  experiments_dynamic_params: string[]
}
