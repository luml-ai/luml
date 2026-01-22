export enum OrbitCollectionTypeEnum {
  model = 'model',
  dataset = 'dataset',
}

export interface OrbitCollection {
  id: string
  orbit_id: string
  description: string
  name: string
  collection_type: OrbitCollectionTypeEnum
  tags: string[]
  total_models: number
  created_at: Date
  updated_at: Date
}

export interface ExtendedOrbitCollection extends OrbitCollection {
  models_metrics: string[]
  models_tags: string[]
}

export interface OrbitCollectionCreator {
  description: string
  name: string
  collection_type?: OrbitCollectionTypeEnum
  tags: string[]
}

export interface GetCollectionsListResponse {
  cursor: string | null
  items: OrbitCollection[]
}

export interface GetCollectionsListParams {
  cursor: string | null
  limit?: number
  sort_by?: 'created_at' | 'name' | 'collection_type' | 'description' | 'total_models'
  order?: 'asc' | 'desc'
  search?: string
}
