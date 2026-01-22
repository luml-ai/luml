import type {
  MlModel,
  MlModelCreator,
  CreateModelResponse,
  UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
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

export interface DeleteModelsResult {
  deleted: string[]
  failed: string[]
}

export type ModelMetadata = TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload

export interface ModelStore {
  requestInfo: Ref<RequestInfo>
  currentModel: Ref<MlModel | null>
  setCurrentModel: (model: MlModel) => void
  resetCurrentModel: () => void
  currentModelTag: Ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>
  currentModelMetadata: Ref<ModelMetadata | null>
  currentModelHtmlBlobUrl: Ref<string | null>
  experimentSnapshotProvider: Ref<ExperimentSnapshotProvider | null>
  initiateCreateModel: (
    data: MlModelCreator,
    requestData?: RequestInfo,
  ) => Promise<CreateModelResponse>
  confirmModelUpload: (payload: UpdateMlModelPayload, requestData?: RequestInfo) => Promise<void>
  cancelModelUpload: (payload: UpdateMlModelPayload, requestData?: RequestInfo) => Promise<void>
  deleteModels: (modelsIds: string[]) => Promise<DeleteModelsResult>
  downloadModel: (modelId: string, name: string) => Promise<void>
  getDownloadUrl: (modelId: string) => Promise<string>
  setCurrentModelTag: (tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) => void
  resetCurrentModelTag: () => void
  setCurrentModelMetadata: (metadata: ModelMetadata) => void
  resetCurrentModelMetadata: () => void
  setCurrentModelHtmlBlobUrl: (htmlFile: string) => void
  resetCurrentModelHtmlBlobUrl: () => void
  setExperimentSnapshotProvider: (provider: ExperimentSnapshotProvider) => void
  resetExperimentSnapshotProvider: () => void
  updateModel: (payload: UpdateMlModelPayload) => Promise<MlModel>
  forceDeleteModels: (modelsIds: string[]) => Promise<DeleteModelsResult>
  getModelsMetrics: (requestData?: RequestInfo) => Promise<string[]>
  getModel: (modelId: string, requestData?: RequestInfo) => Promise<MlModel>
  modelsList: Ref<MlModel[]>
  setModelsList: (list: MlModel[]) => void
}
