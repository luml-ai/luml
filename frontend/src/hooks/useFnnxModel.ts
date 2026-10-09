import { Model } from '@fnnx-ai/web'
import { computed, ref } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'

export const useFnnxModel = () => {
  const buffer = ref<ArrayBuffer | null>(null)
  const model = ref<Model | null>(null)
  const currentTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)
  const modelId = ref<string | null>(null)
  let deinitialization: Promise<void> | null = null
  let cleanupRequested = false

  const getModel = computed(() => model.value)

  async function createModelFromFile(file: File) {
    const availableExtensions = ['.luml', '.dfs']
    const isCorrectExtension = availableExtensions.some((extension) =>
      file.name.endsWith(extension),
    )
    if (!isCorrectExtension) throw new Error('Incorrect file format')
    await removeModel()
    cleanupRequested = false
    buffer.value = await file.arrayBuffer()
    model.value = await Model.fromBuffer(buffer.value)
    currentTag.value = FnnxService.getTypeTag(model.value.getManifest())
    const isPythonModel = model.value.getManifest().variant === 'pyfunc'
    if (isPythonModel) {
      await initPythonModel()
    } else {
      await model.value.warmup()
    }
  }

  async function removeModel() {
    await deinit()
    buffer.value = null
    model.value = null
    currentTag.value = null
  }

  async function initPythonModel() {
    if (!buffer.value) throw new Error('First create a model')
    const result = await DataProcessingWorker.initPythonModel(buffer.value)
    if (result.status === 'success') {
      modelId.value = result.model_id
      if (cleanupRequested) await deinit()
    } else {
      throw new Error(result.error_message)
    }
  }

  async function deinit() {
    cleanupRequested = true
    if (deinitialization) return deinitialization
    if (!modelId.value) return
    deinitialization = DataProcessingWorker.deinitPythonModel(modelId.value)
      .then(() => {
        modelId.value = null
      })
      .finally(() => {
        deinitialization = null
      })
    return deinitialization
  }

  return { currentTag, getModel, modelId, createModelFromFile, removeModel, deinit }
}
