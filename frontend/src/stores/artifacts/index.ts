import type { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type {
  PromptOptimizationModelMetadataPayload,
  TabularModelMetadataPayload,
} from '@/lib/data-processing/interfaces'
import type { ExperimentSnapshotProvider } from '@luml/experiments'
import type {
  Artifact,
  CreateArtifactPayload,
  UpdateArtifactPayload,
} from '@/lib/api/artifacts/interfaces'
import type { ModelMetadata, ArtifactsStore } from './artifacts.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob } from '@/helpers/helpers'
import axios from 'axios'

export const useArtifactsStore = defineStore('artifacts', (): ArtifactsStore => {
  const route = useRoute()

  const currentArtifact = ref<Artifact | null>(null)

  const artifactsList = ref<Artifact[]>([])

  const setArtifactsList = (list: Artifact[]) => {
    artifactsList.value = list
  }

  function setCurrentArtifact(artifact: Artifact) {
    currentArtifact.value = artifact
  }

  function resetCurrentArtifact() {
    currentArtifact.value = null
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

  function initiateCreateArtifact(
    data: CreateArtifactPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    return api.artifacts.create(info.organizationId, info.orbitId, info.collectionId, data)
  }

  async function confirmArtifactUpload(
    payload: UpdateArtifactPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    const result = await api.artifacts.update(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
    setArtifactsList([...artifactsList.value, result])
  }

  async function cancelArtifactUpload(
    payload: UpdateArtifactPayload,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    await api.artifacts.update(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
  }

  async function deleteArtifacts(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteArtifact(id).then(() => id)))
    const deleted: string[] = []
    const failed: string[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        deleted.push(result.value)
      } else {
        failed.push(ids[index])
      }
    })
    removeArtifactsFromList(deleted)
    return { deleted, failed }
  }

  async function deleteArtifact(id: string) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const { url } = await api.artifacts.getDeleteUrl(organizationId, orbitId, collectionId, id)
    await axios.delete(url)
    await api.artifacts.confirmDelete(organizationId, orbitId, collectionId, id)
  }

  async function downloadArtifact(id: string, name: string) {
    const url = await getDownloadUrl(id)
    const response = await fetch(url)
    const blob = await response.blob()
    downloadFileFromBlob(blob, name)
  }

  async function getDownloadUrl(id: string) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const { url } = await api.artifacts.getDownloadUrl(organizationId, orbitId, collectionId, id)
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

  async function updateArtifact(payload: UpdateArtifactPayload) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const result = await api.artifacts.update(
      organizationId,
      orbitId,
      collectionId,
      payload.id,
      payload,
    )
    const newArtifactsList = artifactsList.value.map((a) => (a.id === result.id ? result : a))
    setArtifactsList(newArtifactsList)
    return result
  }

  async function forceDeleteArtifacts(ids: string[]) {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const results = await Promise.allSettled(
      ids.map((id) =>
        api.artifacts.forceDelete(organizationId, orbitId, collectionId, id).then(() => id),
      ),
    )
    const deleted: string[] = []
    const failed: string[] = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        deleted.push(result.value)
      } else {
        failed.push(ids[index])
      }
    })
    removeArtifactsFromList(deleted)
    return { deleted, failed }
  }

  async function getArtifactsExtraValues(requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const collectionDetails = await api.orbitCollections.getCollection(
      info.organizationId,
      info.orbitId,
      info.collectionId,
    )
    return collectionDetails.artifacts_extra_values
  }

  function getArtifact(id: string, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const { organizationId, orbitId, collectionId } = info
    return api.artifacts.getById(organizationId, orbitId, collectionId, id)
  }

  function removeArtifactsFromList(ids: string[]) {
    const newArtifactsList = artifactsList.value.filter((a) => !ids.includes(a.id))
    setArtifactsList(newArtifactsList)
  }

  return {
    currentArtifact,
    setCurrentArtifact,
    resetCurrentArtifact,
    requestInfo,
    currentModelTag,
    currentModelMetadata,
    currentModelHtmlBlobUrl,
    experimentSnapshotProvider,
    initiateCreateArtifact,
    confirmArtifactUpload,
    cancelArtifactUpload,
    deleteArtifacts,
    downloadArtifact,
    getDownloadUrl,
    setCurrentModelTag,
    resetCurrentModelTag,
    setCurrentModelMetadata,
    resetCurrentModelMetadata,
    setCurrentModelHtmlBlobUrl,
    resetCurrentModelHtmlBlobUrl,
    setExperimentSnapshotProvider,
    resetExperimentSnapshotProvider,
    updateArtifact,
    forceDeleteArtifacts,
    getArtifactsExtraValues,
    getArtifact,
    artifactsList,
    setArtifactsList,
  }
})
