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
  id: number
  collection_id: number
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
  tags: string[]
  status: MlModelStatusEnum
  created_at: string
  updated_at: string
}

export interface UpdateMlModelPayload {
  id: number
  file_name: string
  model_name: string
  description: string
  tags: string[]
  status?: MlModelStatusEnum
}

export interface CreateModelResponse {
  model: MlModel
  url: {
    upload_id: string
    parts: CreateModelPart[]
    complete_url: string
  }
}

export interface CreateModelPart {
  part_number: number
  url: string
  start_byte: number
  end_byte: number
  part_size: number
}
