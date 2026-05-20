import type { Manifest } from '@fnnx-ai/common/dist/interfaces'
import { TarHandler } from '@/lib/tar-handler/TarHandler'
import { useArtifactsStore } from '@/stores/artifacts'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import {
  ArtifactStatusEnum,
  type CreateArtifactResponse,
  type CreateArtifactPayload,
  type UpdateArtifactPayload,
  ArtifactTypeEnum,
} from '@/lib/api/artifacts/interfaces'
import { getSha256 } from '@/helpers/helpers'
import axios, { type AxiosProgressEvent } from 'axios'
import { ref } from 'vue'

interface ArtifactData {
  manifest: Manifest
  file_index: Map<string, [number, number]>
  extra_values: any
}

export const useArtifactUpload = () => {
  const artifactsStore = useArtifactsStore()

  const progress = ref<number | null>(null)

  async function upload(
    file: File,
    name: string,
    type: ArtifactTypeEnum,
    description: string,
    tags: string[],
    requestInfo?: { organizationId: string; orbitId: string; collectionId: string },
  ) {
    const { manifest, file_index, extra_values } = await getArtifactData(file, type)
    const artifactBuffer = await file.arrayBuffer()
    const fileHash = await getSha256(artifactBuffer)

    const payload: CreateArtifactPayload = {
      type,
      extra_values,
      manifest,
      file_index: Object.fromEntries(file_index.entries()),
      file_hash: fileHash,
      size: file.size,
      file_name: file.name,
      name,
      description,
      tags,
    }
    const response = await artifactsStore.initiateCreateArtifact(payload, requestInfo)

    await uploadToBucket(response, artifactBuffer, file.name, name, description, tags, requestInfo)

    const confirmPayload: UpdateArtifactPayload = {
      id: response.artifact.id,
      name,
      description,
      tags,
      status: ArtifactStatusEnum.uploaded,
    }
    return artifactsStore.confirmArtifactUpload(confirmPayload, requestInfo)
  }

  async function uploadToBucket(
    data: CreateArtifactResponse,
    buffer: ArrayBuffer,
    fileName: string,
    modelName: string,
    description: string,
    tags: string[],
    requestInfo?: { organizationId: string; orbitId: string; collectionId: string },
  ) {
    try {
      progress.value = 0
      const url = data.upload_details.url
      await axios.put(url, buffer, {
        headers: { 'Content-Type': 'application/octet-stream', 'x-ms-blob-type': 'BlockBlob' },
        onUploadProgress,
      })
    } catch (e) {
      await artifactsStore.cancelArtifactUpload(
        {
          id: data.artifact.id,
          name: modelName,
          description,
          tags,
          status: ArtifactStatusEnum.upload_failed,
        },
        requestInfo,
      )
      throw e
    } finally {
      progress.value = null
    }
  }

  async function getArtifactData(file: File, type: ArtifactTypeEnum): Promise<ArtifactData> {
    if (type === ArtifactTypeEnum.model) {
      return getModelArtifactData(file)
    } else if (type === ArtifactTypeEnum.dataset) {
      return getDatasetArtifactData(file)
    } else if (type === ArtifactTypeEnum.experiment) {
      return getExperimentArtifactData(file)
    }
    throw new Error('Invalid artifact type')
  }

  async function getModelArtifactData(file: File): Promise<ArtifactData> {
    const model = await FnnxService.createModelFromFile(file)
    const manifest = model.getManifest()
    const modelBuffer = await file.arrayBuffer()
    const fileIndex = new TarHandler(modelBuffer).scan()
    const metrics = FnnxService.getRegistryMetrics(model)
    return {
      manifest,
      file_index: fileIndex,
      extra_values: metrics,
    }
  }

  async function getDatasetArtifactData(file: File): Promise<ArtifactData> {
    const buffer = await file.arrayBuffer()
    const handler = new TarHandler(buffer)
    const fileIndex = handler.scan()
    const manifest = handler.getManifest()
    return {
      manifest,
      file_index: fileIndex,
      extra_values: {},
    }
  }

  async function getExperimentArtifactData(file: File): Promise<ArtifactData> {
    const buffer = await file.arrayBuffer()
    const handler = new TarHandler(buffer)
    const fileIndex = handler.scan()
    const manifest = handler.getManifest()
    return {
      manifest,
      file_index: fileIndex,
      extra_values: {},
    }
  }

  function onUploadProgress(event: AxiosProgressEvent) {
    if (event.total) {
      const percentCompleted = Math.round((event.loaded * 100) / event.total)
      progress.value = percentCompleted
    }
  }

  return { progress, upload }
}
