import type { Model } from '@/store/experiments/experiments.interface'
import type { FormInstance } from '@primevue/forms'
import type { ArtifactKind } from './collectionTypes'
import type { PublishTarget } from '@/flow/api/types'

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

/** Where in LUML a model published from a flow cell goes, and its name there. */
export type { PublishTarget } from '@/flow/api/types'

/** Starts the upload as a job; the dialog follows its progress by id. */
export type PublishModel = (target: PublishTarget) => Promise<{ job_id: string }>

export interface UploadModalProps {
  /** The tracker record the upload reads from. Absent when `publish` supplies the file. */
  experimentId?: string
  /** Kept for the Experiments overview, which lists them; the upload itself reads them off the tracker. */
  models?: Model[]
  /** The host renders its own trigger and calls the exposed `open()`. */
  hideTrigger?: boolean
  /**
   * A model that is not on the tracker: a flow cell's. The host packages and
   * sends it; the dialog only asks where in LUML it goes. The type switch and
   * the embed toggle are experiment questions and stay hidden.
   */
  publish?: PublishModel
  /** What the name field opens with. */
  defaultName?: string
}

export interface CollectionFieldProps {
  fieldName: string
  organizationId?: string | null
  orbitId?: string | null
  formRef: FormInstance | undefined
  /** What the upload will put in the collection; collections that refuse it are left out. */
  requiredKinds: ArtifactKind[]
}

export interface CollectionFieldEmits {
  (e: 'change-collection', collection: CollectionInfo | undefined): void
}
