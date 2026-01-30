import type {
  Artifact,
  CreateArtifactPayload,
  CreateArtifactResponse,
  UpdateArtifactPayload,
} from '@/lib/api/artifacts/interfaces'
import type { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type {
  TabularModelMetadataPayload,
  PromptOptimizationModelMetadataPayload,
} from '@/lib/data-processing/interfaces'
import type { ExperimentSnapshotProvider } from '@/modules/experiment-snapshot'
import type { Ref } from 'vue'

export interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionId: string
}

export interface DeleteArtifactsResult {
  deleted: string[]
  failed: string[]
}

export type ModelMetadata = TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload

export interface ArtifactsStore {
  requestInfo: Ref<RequestInfo>
  currentArtifact: Ref<Artifact | null>
  setCurrentArtifact: (model: Artifact) => void
  resetCurrentArtifact: () => void
  currentModelTag: Ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>
  currentModelMetadata: Ref<ModelMetadata | null>
  currentModelHtmlBlobUrl: Ref<string | null>
  experimentSnapshotProvider: Ref<ExperimentSnapshotProvider | null>
  initiateCreateArtifact: (
    data: CreateArtifactPayload,
    requestData?: RequestInfo,
  ) => Promise<CreateArtifactResponse>
  confirmArtifactUpload: (
    payload: UpdateArtifactPayload,
    requestData?: RequestInfo,
  ) => Promise<void>
  cancelArtifactUpload: (payload: UpdateArtifactPayload, requestData?: RequestInfo) => Promise<void>
  deleteArtifacts: (ids: string[]) => Promise<DeleteArtifactsResult>
  downloadArtifact: (id: string, name: string) => Promise<void>
  getDownloadUrl: (id: string) => Promise<string>
  setCurrentModelTag: (tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) => void
  resetCurrentModelTag: () => void
  setCurrentModelMetadata: (metadata: ModelMetadata) => void
  resetCurrentModelMetadata: () => void
  setCurrentModelHtmlBlobUrl: (htmlFile: string) => void
  resetCurrentModelHtmlBlobUrl: () => void
  setExperimentSnapshotProvider: (provider: ExperimentSnapshotProvider) => void
  resetExperimentSnapshotProvider: () => void
  updateArtifact: (payload: UpdateArtifactPayload) => Promise<Artifact>
  forceDeleteArtifacts: (ids: string[]) => Promise<DeleteArtifactsResult>
  getArtifactsExtraValues: (requestData?: RequestInfo) => Promise<string[]>
  getArtifact: (id: string, requestData?: RequestInfo) => Promise<Artifact>
  artifactsList: Ref<Artifact[]>
  setArtifactsList: (list: Artifact[]) => void
}
