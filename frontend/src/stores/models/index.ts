import type { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type {
  PromptOptimizationModelMetadataPayload,
  TabularModelMetadataPayload,
} from '@/lib/data-processing/interfaces'
import type {
  MlModel,
  MlModelCreator,
  UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
import type { ExperimentSnapshotProvider } from '@/modules/experiment-snapshot'
import type { ModelMetadata, ModelStore } from './model.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob } from '@/helpers/helpers'
import axios from 'axios'

export const useModelsStore = defineStore('models', (): ModelStore => {
  const route = useRoute()

  const currentModel = ref<MlModel | null>(null)

  const modelsList = ref<MlModel[]>([])

  const setModelsList = (list: MlModel[]) => {
    modelsList.value = list
  }

  function setCurrentModel(model: MlModel) {
    currentModel.value = model
  }

  function resetCurrentModel() {
    currentModel.value = null
  }

  const currentModelTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)
  const currentModelMetadata = ref<ModelMetadata | null>(null)
  const currentModelHtmlBlobUrl = ref<string | null>(null)
  const experimentSnapshotProvider = ref<ExperimentSnapshotProvider | null>(null)

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string')
      throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    if (typeof route.params.collectionId !== 'string') throw new Error('Collection was not found')

    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
      collectionId: route.params.collectionId,
    }
  })

  function initiateCreateModel(data: MlModelCreator, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    return api.mlModels.createModel(info.organizationId, info.orbitId, info.collectionId, data)
  }

  async function confirmModelUpload(
    payload: UpdateMlModelPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    const model = await api.mlModels.updateModel(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
    setModelsList([...modelsList.value, model])
  }

  async function cancelModelUpload(
    payload: UpdateMlModelPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    await api.mlModels.updateModel(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
  }

  async function deleteModels(modelsIds: string[]) {
    const results = await Promise.allSettled(modelsIds.map((id) => deleteModel(id).then(() => id)))
    const deleted: string[] = []
    const failed: string[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        deleted.push(result.value)
      } else {
        failed.push(modelsIds[index])
      }
    })
    removeModelsFromList(deleted)
    return { deleted, failed }
  }

  async function deleteModel(modelId: string) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const { url } = await api.mlModels.getModelDeleteUrl(
      organizationId,
      orbitId,
      collectionId,
      modelId,
    )
    await axios.delete(url)
    await api.mlModels.confirmModelDelete(organizationId, orbitId, collectionId, modelId)
  }

  async function downloadModel(modelId: string, name: string) {
    const url = await getDownloadUrl(modelId)
    const response = await fetch(url)
    const blob = await response.blob()
    downloadFileFromBlob(blob, name)
  }

  async function getDownloadUrl(modelId: string) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const { url } = await api.mlModels.getModelDownloadUrl(
      organizationId,
      orbitId,
      collectionId,
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
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const model = await api.mlModels.updateModel(
      organizationId,
      orbitId,
      collectionId,
      payload.id,
      payload,
    )
    const newModelsList = modelsList.value.map((m) => (m.id === model.id ? model : m))
    setModelsList(newModelsList)
    return model
  }

  async function forceDeleteModels(modelsIds: string[]) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const results = await Promise.allSettled(
      modelsIds.map((id) =>
        api.mlModels.forceDelete(organizationId, orbitId, collectionId, id).then(() => id),
      ),
    )
    const deleted: string[] = []
    const failed: string[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        deleted.push(result.value)
      } else {
        failed.push(modelsIds[index])
      }
    })
    removeModelsFromList(deleted)
    return { deleted, failed }
  }

  async function getModelsMetrics(requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const collectionDetails = await api.orbitCollections.getCollection(
      info.organizationId,
      info.orbitId,
      info.collectionId,
    )
    return collectionDetails.models_metrics
  }

  function getModel(modelId: string, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const { organizationId, orbitId, collectionId } = info
    return api.mlModels.getModelById(organizationId, orbitId, collectionId, modelId)
  }

  function removeModelsFromList(modelsIds: string[]) {
    const newModelsList = modelsList.value.filter((model) => !modelsIds.includes(model.id))
    setModelsList(newModelsList)
  }

  return {
    currentModel,
    setCurrentModel,
    resetCurrentModel,
    requestInfo,
    currentModelTag,
    currentModelMetadata,
    currentModelHtmlBlobUrl,
    experimentSnapshotProvider,
    initiateCreateModel,
    confirmModelUpload,
    cancelModelUpload,
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
    forceDeleteModels,
    getModelsMetrics,
    getModel,
    modelsList,
    setModelsList,
  }
})
