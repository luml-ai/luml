import type { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type {
  PromptOptimizationModelMetadataPayload,
  TabularModelMetadataPayload,
} from '@/lib/data-processing/interfaces'
import type {
  CreateModelResponse,
  MlModel,
  MlModelCreator,
  UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
import { defineStore } from 'pinia'
import { computed, ref, type Ref } from 'vue'
import { dataforceApi } from '@/lib/api'
import axios from 'axios'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob } from '@/helpers/helpers'
import type { ExperimentSnapshotProvider } from '@/modules/experiment-snapshot'

// TODO: Separate interfaces
interface RequestInfo {
  organizationId: number
  orbitId: number
  collectionId: number
}

interface ModelStore {
  modelsList: Ref<MlModel[]>
  requestInfo: Ref<RequestInfo>
  currentModelTag: Ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>
  currentModelMetadata: Ref<
    TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload | null
  >
  currentModelHtmlBlobUrl: Ref<string | null>
  experimentSnapshotProvider: Ref<ExperimentSnapshotProvider | null>
  initiateCreateModel: (
    data: MlModelCreator,
    requestData?: {
      organizationId: number
      orbitId: number
      collectionId: number
    },
  ) => Promise<CreateModelResponse>
  confirmModelUpload: (payload: UpdateMlModelPayload, requestData?: RequestInfo) => Promise<void>
  loadModelsList: (
    organizationId?: number,
    orbitId?: number,
    collectionId?: number,
  ) => Promise<void>
  cancelModelUpload: (
    payload: UpdateMlModelPayload,
    requestData?: {
      organizationId: number
      orbitId: number
      collectionId: number
    },
  ) => Promise<void>
  resetList: () => void
  deleteModels: (modelsIds: number[]) => Promise<{
    deleted: number[]
    failed: number[]
  }>
  downloadModel: (modelId: number, name: string) => Promise<void>
  getDownloadUrl: (modelId: number) => Promise<string>
  setCurrentModelTag: (tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) => void
  resetCurrentModelTag: () => void
  setCurrentModelMetadata: (
    metadata: TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload,
  ) => void
  resetCurrentModelMetadata: () => void
  setCurrentModelHtmlBlobUrl: (htmlFile: string) => void
  resetCurrentModelHtmlBlobUrl: () => void
  setExperimentSnapshotProvider: (provider: ExperimentSnapshotProvider) => void
  resetExperimentSnapshotProvider: () => void
  updateModel: (payload: UpdateMlModelPayload) => Promise<void>
}

export const useModelsStore = defineStore('models', (): ModelStore => {
  const route = useRoute()

  const modelsList = ref<MlModel[]>([])
  const currentModelTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)
  const currentModelMetadata = ref<
    TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload | null
  >(null)
  const currentModelHtmlBlobUrl = ref<string | null>(null)
  const experimentSnapshotProvider = ref<ExperimentSnapshotProvider | null>(null)

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string')
      throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    if (typeof route.params.collectionId !== 'string') throw new Error('Collection was not found')

    return {
      organizationId: +route.params.organizationId,
      orbitId: +route.params.id,
      collectionId: +route.params.collectionId,
    }
  })

  async function loadModelsList(organizationId?: number, orbitId?: number, collectionId?: number) {
    modelsList.value = await dataforceApi.mlModels.getModelsList(
      organizationId ?? requestInfo.value.organizationId,
      orbitId ?? requestInfo.value.orbitId,
      collectionId ?? requestInfo.value.collectionId,
    )
  }

  function initiateCreateModel(data: MlModelCreator, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    return dataforceApi.mlModels.createModel(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      data,
    )
  }

  async function confirmModelUpload(
    payload: UpdateMlModelPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    const model = await dataforceApi.mlModels.updateModel(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
    modelsList.value.push(model)
  }

  async function cancelModelUpload(
    payload: UpdateMlModelPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    await dataforceApi.mlModels.updateModel(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
  }

  function resetList() {
    modelsList.value = []
  }

  async function deleteModels(modelsIds: number[]) {
    const results = await Promise.allSettled(modelsIds.map((id) => deleteModel(id).then(() => id)))
    const deleted: number[] = []
    const failed: number[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        deleted.push(result.value)
      } else {
        failed.push(modelsIds[index])
      }
    })
    modelsList.value = modelsList.value.filter((model) => !deleted.includes(model.id))
    return { deleted, failed }
  }

  async function deleteModel(modelId: number) {
    const { url } = await dataforceApi.mlModels.getModelDeleteUrl(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
    await axios.delete(url)
    await dataforceApi.mlModels.confirmModelDelete(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
  }

  async function downloadModel(modelId: number, name: string) {
    const url = await getDownloadUrl(modelId)
    const response = await fetch(url)
    const blob = await response.blob()
    downloadFileFromBlob(blob, name)
  }

  async function getDownloadUrl(modelId: number) {
    const { url } = await dataforceApi.mlModels.getModelDownloadUrl(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      modelId,
    )
    return url
  }

  function setCurrentModelTag(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) {
    currentModelTag.value = tag
  }

  function resetCurrentModelTag() {
    currentModelTag.value = null
  }

  function setCurrentModelMetadata(
    metadata: TabularModelMetadataPayload | PromptOptimizationModelMetadataPayload,
  ) {
    currentModelMetadata.value = metadata
  }

  function resetCurrentModelMetadata() {
    currentModelMetadata.value = null
  }

  function setCurrentModelHtmlBlobUrl(htmlFile: string) {
    currentModelHtmlBlobUrl.value = htmlFile
  }

  function resetCurrentModelHtmlBlobUrl() {
    currentModelHtmlBlobUrl.value = null
  }

  function setExperimentSnapshotProvider(provider: ExperimentSnapshotProvider) {
    experimentSnapshotProvider.value = provider
  }

  function resetExperimentSnapshotProvider() {
    experimentSnapshotProvider.value = null
  }

  async function updateModel(payload: UpdateMlModelPayload) {
    const result = await dataforceApi.mlModels.updateModel(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      payload.id,
      payload,
    )
    modelsList.value = modelsList.value.map(model => {
      return model.id === result.id ? result : model
    })
  }

  return {
    modelsList,
    requestInfo,
    currentModelTag,
    currentModelMetadata,
    currentModelHtmlBlobUrl,
    experimentSnapshotProvider,
    initiateCreateModel,
    confirmModelUpload,
    loadModelsList,
    cancelModelUpload,
    resetList,
    deleteModels,
    downloadModel,
    getDownloadUrl,
    setCurrentModelTag,
    resetCurrentModelTag,
    setCurrentModelMetadata,
    resetCurrentModelMetadata,
    setCurrentModelHtmlBlobUrl,
    resetCurrentModelHtmlBlobUrl,
    setExperimentSnapshotProvider,
    resetExperimentSnapshotProvider,
    updateModel,
  }
})
