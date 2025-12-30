import type { Manifest } from '@fnnx/common/dist/interfaces'

export interface FileIndex extends Record<string, [number, number]> {}

export enum MlModelStatusEnum {
  pending_upload = 'pending_upload',
  uploaded = 'uploaded',
  pending_deletion = 'pending_deletion',
  upload_failed = 'upload_failed',
  deletion_failed = 'deletion_failed',
}

export interface MlModelCreator {
  metrics: Record<string, object>
  manifest: Manifest
  file_index: FileIndex
  file_hash: string
  size: number
  file_name: string
  model_name: string
  description: string
  tags: string[]
}

export interface MlModel {
  id: string
  collection_id: string
  file_name: string
  model_name: string
  description: string
  metrics: Record<string, number | string>
  manifest: Manifest
  file_hash: string
  file_index: FileIndex
  bucket_location: string
  size: number
  unique_identifier: string
  tags?: string[]
  status: MlModelStatusEnum
  created_at: string
  updated_at: string
}

export interface UpdateMlModelPayload {
  id: string
  file_name: string
  model_name: string
  description: string
  tags: string[]
  status?: MlModelStatusEnum
}

export interface CreateModelResponse {
  model: MlModel
  upload_details: {
    url: string
    multipart: boolean
    bucket_location: string
    bucket_secret_id: string
  }
}
