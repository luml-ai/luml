import type { Manifest } from '@fnnx-ai/common/dist/interfaces'

export interface FileIndex extends Record<string, [number, number]> {}

export enum ArtifactStatusEnum {
  pending_upload = 'pending_upload',
  uploaded = 'uploaded',
  pending_deletion = 'pending_deletion',
  upload_failed = 'upload_failed',
  deletion_failed = 'deletion_failed',
}

export enum ArtifactTypeEnum {
  model = 'model',
  dataset = 'dataset',
  experiment = 'experiment',
}

export interface CreateArtifactPayload {
  type: ArtifactTypeEnum
  extra_values: Record<string, object>
  manifest: Manifest
  file_index: FileIndex
  file_hash: string
  size: number
  file_name: string
  name: string
  description: string
  tags: string[]
}

export interface Artifact {
  type: ArtifactTypeEnum
  id: string
  collection_id: string
  file_name: string
  name: string
  description: string
  extra_values: Record<string, number | string>
  manifest: Manifest
  file_hash: string
  file_index: FileIndex
  bucket_location: string
  size: number
  unique_identifier: string
  tags?: string[]
  status: ArtifactStatusEnum
  created_at: string
  updated_at: string
}

export interface UpdateArtifactPayload {
  id: string
  file_name: string
  name: string
  description: string
  tags: string[]
  status?: ArtifactStatusEnum
}

export interface CreateArtifactResponse {
  artifact: Artifact
  upload_details: {
    url: string
    multipart: boolean
    bucket_location: string
    bucket_secret_id: string
  }
}

export interface GetArtifactsListResponse {
  cursor: string | null
  items: Artifact[]
}

export interface GetArtifactsListParams {
  cursor: string | null
  limit?: number
  sort_by?: 'created_at' | 'name' | 'size' | 'description' | 'status'
  order?: 'asc' | 'desc'
  types?: ArtifactTypeEnum[]
}

export type ModelArtifact = Artifact

export interface DatasetManifest {
  artifact_type: 'dataset'
  variant: string
  name: string
  description: string | null
  version: string | null
  producer_name: string
  producer_version: string
  producer_tags: string[]
  payload: DatasetPayload
}

export interface DatasetPayload {
  subsets: Record<string, Subset>
  data_dir: string
  library_version: string
  total_rows: number
  file_format: string
}

export interface Subset {
  splits: Record<string, Split>
}

export interface Split {
  num_rows: number
  num_chunks: number
  chunk_files: string[]
  file_format: 'parquet' | 'csv'
}
