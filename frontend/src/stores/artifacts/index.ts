import { FnnxService, type FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import type { ExperimentSnapshotProvider } from '@luml/experiments'
import type {
  Artifact,
  CreateArtifactPayload,
  FileIndex,
  UpdateArtifactPayload,
} from '@/lib/api/artifacts/interfaces'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { ModelMetadata, RequestInfo } from './artifacts.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import { downloadFileFromBlob, getErrorMessage } from '@/helpers/helpers'
import axios from 'axios'
import { ModelDownloader } from '@/lib/bucket-service'

export type ArtifactAttachmentsStatus = 'idle' | 'loading' | 'available' | 'empty' | 'error'

const MAX_ATTACHMENTS_INDEX_SIZE = 1024 * 1024

export const useArtifactsStore = defineStore('artifacts', () => {
  const route = useRoute()

  const currentArtifact = ref<Artifact | null>(null)

  const attachmentsIndex = ref<FileIndex | null>(null)
  const attachmentsDownloader = ref<ModelDownloader | null>(null)
  const attachmentsStatus = ref<ArtifactAttachmentsStatus>('idle')
  const attachmentsError = ref<string | null>(null)
  let attachmentsLoadVersion = 0

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
    resetCurrentArtifactAttachments()
  }

  function resetCurrentArtifactAttachments() {
    attachmentsLoadVersion += 1
    attachmentsIndex.value = null
    attachmentsDownloader.value = null
    attachmentsStatus.value = 'idle'
    attachmentsError.value = null
  }

  async function loadCurrentArtifactAttachments(artifact: Artifact) {
    const loadVersion = ++attachmentsLoadVersion
    attachmentsIndex.value = null
    attachmentsDownloader.value = null
    attachmentsStatus.value = 'loading'
    attachmentsError.value = null

    const fileIndex = artifact.file_index
    const tarPath = FnnxService.findAttachmentsTarPath(fileIndex)
    const indexPath = FnnxService.findAttachmentsIndexPath(fileIndex)

    if (
      (artifact.type !== ArtifactTypeEnum.model && artifact.type !== ArtifactTypeEnum.experiment) ||
      !tarPath ||
      !indexPath
    ) {
      if (loadVersion === attachmentsLoadVersion) attachmentsStatus.value = 'empty'
      return
    }

    try {
      const [indexOffset, indexSize] = fileIndex[indexPath]
      const indexEnd = indexOffset + indexSize
      const [tarOffset, tarSize] = fileIndex[tarPath]
      const tarEnd = tarOffset + tarSize
      if (
        !Number.isSafeInteger(artifact.size) ||
        artifact.size < 0 ||
        !Number.isSafeInteger(indexOffset) ||
        !Number.isSafeInteger(indexSize) ||
        indexOffset < 0 ||
        indexSize <= 0 ||
        indexSize > MAX_ATTACHMENTS_INDEX_SIZE ||
        !Number.isSafeInteger(indexEnd) ||
        indexEnd > artifact.size ||
        !Number.isSafeInteger(tarOffset) ||
        !Number.isSafeInteger(tarSize) ||
        tarOffset < 0 ||
        tarSize < 0 ||
        !Number.isSafeInteger(tarEnd) ||
        tarEnd > artifact.size
      ) {
        throw new Error('Attachment index has an invalid range')
      }

      const url = await getDownloadUrl(artifact.id)
      const downloader = new ModelDownloader(url)
      const index = await downloader.getFileFromBucket<unknown>(fileIndex, indexPath)

      if (!FnnxService.isValidAttachmentsIndex(index, tarSize)) {
        throw new Error('Attachment index has invalid content')
      }

      if (loadVersion !== attachmentsLoadVersion || currentArtifact.value?.id !== artifact.id) {
        return
      }

      if (!FnnxService.hasAttachments(index)) {
        attachmentsStatus.value = 'empty'
      } else {
        attachmentsIndex.value = index
        attachmentsDownloader.value = downloader
        attachmentsStatus.value = 'available'
      }
    } catch (error) {
      if (loadVersion !== attachmentsLoadVersion || currentArtifact.value?.id !== artifact.id) {
        return
      }

      attachmentsError.value = getErrorMessage(error, 'Failed to check attachments')
      attachmentsStatus.value = 'error'
    }
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
    attachmentsIndex,
    attachmentsDownloader,
    attachmentsStatus,
    attachmentsError,
    loadCurrentArtifactAttachments,
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
