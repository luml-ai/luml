import type { Model } from '@/store/experiments/experiments.interface'
import type { FormInstance } from '@primevue/forms'

export enum UploadTypeEnum {
  AUTO = 'auto',
  MODEL = 'model',
  EXPERIMENT = 'experiment',
}

export interface OrganizationInfo {
  id: string
  name: string
  logo: string | null
  created_at: string
  updated_at: string | null
}

export interface OrbitInfo {
  id: string
  name: string
  organization_id: string
  bucket_secret_id: string
  total_members: number | null
  total_collections: number | null
  created_at: string
  updated_at: string | null
}

export interface CollectionInfo {
  id: string
  orbit_id: string
  description: string
  name: string
  type: string
  tags: string[]
  total_artifacts: number
  created_at: string
  updated_at: string | null
}

export interface UploadArtifactPayload {
  upload_type: UploadTypeEnum
  embed_experiment: boolean
  experiment_id: string
  organization_id: string
  orbit_id: string
  collection_id: string
  artifact: UploadedArtifactInfo
}

export interface UploadedArtifactInfo {
  name: string
  description: string
  tags: string[]
}

export interface UploadModalProps {
  experimentId: string
  models: Model[]
}

export interface CollectionFieldProps {
  fieldName: string
  organizationId?: string | null
  orbitId?: string | null
  formRef: FormInstance | undefined
}

export interface CollectionFieldEmits {
  (e: 'change-collection', collection: CollectionInfo | undefined): void
}
