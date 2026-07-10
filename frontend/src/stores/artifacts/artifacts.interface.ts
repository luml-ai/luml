import type {
  TabularModelMetadataPayload,
  PromptOptimizationModelMetadataPayload,
  ForecastingModelMetadataPayload,
} from '@/lib/data-processing/interfaces'

export interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionId: string
}

export interface DeleteArtifactsResult {
  deleted: string[]
  failed: string[]
}

export type ModelMetadata =
  | TabularModelMetadataPayload
  | PromptOptimizationModelMetadataPayload
  | ForecastingModelMetadataPayload
