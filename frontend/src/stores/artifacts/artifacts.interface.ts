import type {
  TabularModelMetadataPayload,
  PromptOptimizationModelMetadataPayload,
  ForecastingModelMetadataPayload,
} from '@/lib/data-processing/interfaces'
import type { ArtifactDeleteFailure } from '@/lib/api/artifacts/interfaces'

export interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionId: string
}

export interface DeleteArtifactsResult {
  deleted: string[]
  failed: ArtifactDeleteFailure[]
  error?: unknown
  notCompleted?: string[]
}

export type ModelMetadata =
  | TabularModelMetadataPayload
  | PromptOptimizationModelMetadataPayload
  | ForecastingModelMetadataPayload
