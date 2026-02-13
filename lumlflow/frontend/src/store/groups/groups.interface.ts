export interface Group {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
  tags: string[] | null
}

export type UpdateGroupPayload = Pick<Group, 'name' | 'description' | 'tags'>
