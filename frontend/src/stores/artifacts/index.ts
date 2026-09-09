import type { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type { ExperimentSnapshotProvider } from '@luml/experiments'
import {
  ArtifactStatusEnum,
  type Artifact,
  type ArtifactDeleteFailure,
  type ArtifactDeleteUrl,
  type ArtifactsDeleteResponse,
  type ArtifactsDeleteUrlsResponse,
  type CreateArtifactPayload,
  type UpdateArtifactPayload,
} from '@/lib/api/artifacts/interfaces'
import type { DeleteArtifactsResult, ModelMetadata, RequestInfo } from './artifacts.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob } from '@/helpers/helpers'
import axios from 'axios'

const ARTIFACT_DELETE_CHUNK_SIZE = 100

export const useArtifactsStore = defineStore('artifacts', () => {
  const route = useRoute()

  const currentArtifact = ref<Artifact | null>(null)

  const artifactsList = ref<Artifact[]>([])

  const modelsWithActiveDeploymentsForDeletion = ref<Artifact[]>([])

  const setArtifactsList = (list: Artifact[]) => {
    artifactsList.value = list
  }

  function setCurrentArtifact(artifact: Artifact) {
    currentArtifact.value = artifact
  }

  function resetCurrentArtifact() {
    currentArtifact.value = null
  }

  async function refreshCurrentArtifact() {
    if (!currentArtifact.value) return
    const artifact = await getArtifact(currentArtifact.value.id)
    setCurrentArtifact(artifact)
  }

  const currentModelTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)
  const currentModelMetadata = ref<ModelMetadata | null>(null)
  const currentModelHtmlBlobUrl = ref<string | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const experimentSnapshotProvider = ref<any>(null)

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

  function initiateCreateArtifact(data: CreateArtifactPayload, requestData?: RequestInfo) {
    const info = requestData ? requestData : requestInfo.value
    return api.artifacts.create(info.organizationId, info.orbitId, info.collectionId, data)
  }

  async function confirmArtifactUpload(payload: UpdateArtifactPayload, requestData?: RequestInfo) {
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

  async function cancelArtifactUpload(payload: UpdateArtifactPayload, requestData?: RequestInfo) {
    const info = requestData ? requestData : requestInfo.value
    await api.artifacts.update(
      info.organizationId,
      info.orbitId,
      info.collectionId,
      payload.id,
      payload,
    )
  }

  async function deleteArtifacts(ids: string[]): Promise<DeleteArtifactsResult> {
    return processArtifactDeletion(ids, false)
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

  function setCurrentModelMetadata(metadata: ModelMetadata) {
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

  async function forceDeleteArtifacts(ids: string[]): Promise<DeleteArtifactsResult> {
    return processArtifactDeletion(ids, true)
  }

  async function processArtifactDeletion(
    ids: string[],
    force: boolean,
  ): Promise<DeleteArtifactsResult> {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    const distinctIds = [...new Set(ids)]
    const result: DeleteArtifactsResult = { deleted: [], failed: [] }

    for (let start = 0; start < distinctIds.length; start += ARTIFACT_DELETE_CHUNK_SIZE) {
      const chunk = distinctIds.slice(start, start + ARTIFACT_DELETE_CHUNK_SIZE)
      const laterIds = distinctIds.slice(start + ARTIFACT_DELETE_CHUNK_SIZE)

      if (force) {
        try {
          const response = await api.artifacts.confirmDelete(
            organizationId,
            orbitId,
            collectionId,
            chunk,
            true,
          )
          mergeConfirmationResponse(result, response)
        } catch (error) {
          return { ...result, error, notCompleted: [...chunk, ...laterIds] }
        }
        continue
      }

      let deletionRequest: ArtifactsDeleteUrlsResponse
      try {
        deletionRequest = await api.artifacts.requestDeleteUrls(
          organizationId,
          orbitId,
          collectionId,
          chunk,
        )
      } catch (error) {
        return { ...result, error, notCompleted: [...chunk, ...laterIds] }
      }

      updateArtifactStatuses(
        deletionRequest.urls.map(({ artifact_id }) => artifact_id),
        ArtifactStatusEnum.pending_deletion,
      )
      mergeFailures(result, deletionRequest.failed)

      const deletedFromBucket = await deleteArtifactsFromBucket(deletionRequest.urls, result)
      if (!deletedFromBucket.length) continue

      try {
        const response = await api.artifacts.confirmDelete(
          organizationId,
          orbitId,
          collectionId,
          deletedFromBucket,
        )
        mergeConfirmationResponse(result, response)
      } catch (error) {
        return { ...result, error, notCompleted: [...deletedFromBucket, ...laterIds] }
      }
    }

    return result
  }

  async function deleteArtifactsFromBucket(
    urls: ArtifactDeleteUrl[],
    result: DeleteArtifactsResult,
  ): Promise<string[]> {
    const outcomes = await Promise.all(
      urls.map(async (entry) => ({ entry, deleted: await deleteArtifactFromBucket(entry.url) })),
    )
    const deleted: string[] = []

    for (const { entry, deleted: objectDeleted } of outcomes) {
      if (objectDeleted) {
        deleted.push(entry.artifact_id)
        continue
      }

      const failure: ArtifactDeleteFailure = {
        artifact_id: entry.artifact_id,
        name: entry.name,
        reason: 'storage_error',
        deployments: [],
        tracks: [],
      }
      await markStorageFailure(entry.artifact_id)
      result.failed.push(failure)
    }

    return deleted
  }

  async function deleteArtifactFromBucket(url: string): Promise<boolean> {
    try {
      const response = await axios.delete(url)
      return (response.status >= 200 && response.status < 300) || response.status === 404
    } catch (error) {
      return getResponseStatus(error) === 404
    }
  }

  async function markStorageFailure(artifactId: string): Promise<void> {
    const { organizationId, orbitId, collectionId } = requestInfo.value
    try {
      await api.artifacts.update(organizationId, orbitId, collectionId, artifactId, {
        id: artifactId,
        status: ArtifactStatusEnum.deletion_failed,
      })
      updateArtifactStatuses([artifactId], ArtifactStatusEnum.deletion_failed)
    } catch (error) {
      console.error(`Failed to set artifact ${artifactId} status to deletion_failed`, error)
    }
  }

  function mergeConfirmationResponse(
    result: DeleteArtifactsResult,
    response: ArtifactsDeleteResponse,
  ): void {
    result.deleted.push(...response.deleted)
    removeArtifactsFromList(response.deleted)
    mergeFailures(result, response.failed)
  }

  function mergeFailures(result: DeleteArtifactsResult, failures: ArtifactDeleteFailure[]): void {
    const notFoundIds = failures
      .filter(({ reason }) => reason === 'not_found')
      .map(({ artifact_id }) => artifact_id)
    removeArtifactsFromList(notFoundIds)

    const visibleFailures = failures.filter(({ reason }) => reason !== 'not_found')
    result.failed.push(...visibleFailures)
    updateArtifactStatuses(
      visibleFailures
        .filter(({ reason }) => reason === 'storage_error')
        .map(({ artifact_id }) => artifact_id),
      ArtifactStatusEnum.deletion_failed,
    )
  }

  function getResponseStatus(error: unknown): number | undefined {
    if (typeof error !== 'object' || error === null || !('response' in error)) return undefined
    const response = (error as { response?: { status?: unknown } }).response
    return typeof response?.status === 'number' ? response.status : undefined
  }

  function updateArtifactStatuses(ids: string[], status: ArtifactStatusEnum): void {
    const artifactIds = new Set(ids)
    if (!artifactIds.size) return
    setArtifactsList(
      artifactsList.value.map((artifact) =>
        artifactIds.has(artifact.id) ? { ...artifact, status } : artifact,
      ),
    )
  }

  async function getArtifactsExtraValues(requestData?: RequestInfo) {
    const info = requestData ? requestData : requestInfo.value
    const collectionDetails = await api.orbitCollections.getCollection(
      info.organizationId,
      info.orbitId,
      info.collectionId,
    )
    return collectionDetails.artifacts_extra_values
  }

  function getArtifact(id: string, requestData?: RequestInfo) {
    const info = requestData ? requestData : requestInfo.value
    const { organizationId, orbitId, collectionId } = info
    return api.artifacts.getById(organizationId, orbitId, collectionId, id)
  }

  function removeArtifactsFromList(ids: string[]) {
    const newArtifactsList = artifactsList.value.filter((a) => !ids.includes(a.id))
    setArtifactsList(newArtifactsList)
  }

  function setModelsWithActiveDeploymentsForDeletion(artifacts: Artifact[]) {
    modelsWithActiveDeploymentsForDeletion.value = artifacts
  }

  function resetModelsWithActiveDeploymentsForDeletion() {
    modelsWithActiveDeploymentsForDeletion.value = []
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
    setModelsWithActiveDeploymentsForDeletion,
    resetModelsWithActiveDeploymentsForDeletion,
    modelsWithActiveDeploymentsForDeletion,
    refreshCurrentArtifact,
  }
})
