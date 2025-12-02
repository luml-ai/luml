import { TarHandler } from '@/lib/tar-handler/TarHandler'
import { useModelsStore } from '@/stores/models'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import {
  MlModelStatusEnum,
  type CreateModelResponse,
  type MlModelCreator,
  type UpdateMlModelPayload,
} from '@/lib/api/orbit-ml-models/interfaces'
import { getSha256 } from '@/helpers/helpers'
import axios, { type AxiosProgressEvent } from 'axios'
import { ref } from 'vue'

export const useModelUpload = () => {
  const modelsStore = useModelsStore()

  const progress = ref<number | null>(null)

  async function upload(
    file: File,
    name: string,
    description: string,
    tags: string[],
    requestInfo?: { organizationId: string; orbitId: string; collectionId: string },
  ) {
    const model = await FnnxService.createModelFromFile(file)
    const manifest = model.getManifest()
    const modelBuffer = await file.arrayBuffer()
    const fileIndex = new TarHandler(modelBuffer).scan()
    const metrics = FnnxService.getRegistryMetrics(model)
    const fileHash = await getSha256(modelBuffer)

    const payload: MlModelCreator = {
      metrics: metrics,
      manifest,
      file_index: Object.fromEntries(fileIndex.entries()),
      file_hash: fileHash,
      size: file.size,
      file_name: file.name,
      model_name: name,
      description,
      tags,
    }
    const response = await modelsStore.initiateCreateModel(payload, requestInfo)

    await uploadToBucket(response, modelBuffer, file.name, name, description, tags, requestInfo)

    const confirmPayload: UpdateMlModelPayload = {
      id: response.model.id,
      file_name: file.name,
      model_name: name,
      description,
      tags,
      status: MlModelStatusEnum.uploaded,
    }
    return modelsStore.confirmModelUpload(confirmPayload, requestInfo)
  }

  async function uploadToBucket(
    data: CreateModelResponse,
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
        headers: { 'Content-Type': 'application/octet-stream' },
        onUploadProgress,
      })
    } catch (e) {
      await modelsStore.cancelModelUpload(
        {
          id: data.model.id,
          file_name: fileName,
          model_name: modelName,
          description,
          tags,
          status: MlModelStatusEnum.upload_failed,
        },
        requestInfo,
      )
      throw e
    } finally {
      progress.value = null
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
