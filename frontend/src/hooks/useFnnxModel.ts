import { Model } from '@fnnx/web'
import { computed, ref } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'

export const useFnnxModel = () => {
  const buffer = ref<ArrayBuffer | null>(null)
  const model = ref<Model | null>(null)
  const currentTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)
  const modelId = ref<string | null>(null)

  const getModel = computed(() => model.value)

  async function createModelFromFile(file: File) {
    if (!file.name.endsWith('.dfs')) throw new Error('Incorrect file format')
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

  function removeModel() {
    buffer.value = null
    model.value = null
    currentTag.value = null
    deinit()
  }

  async function initPythonModel() {
    if (!buffer.value) throw new Error('First create a model')
    const result = await DataProcessingWorker.initPythonModel(buffer.value)
    if (result.status === 'success') {
      modelId.value = result.model_id
    } else {
      throw new Error(result.error_message)
    }
  }

  async function deinit() {
    if (!modelId.value) return
    return DataProcessingWorker.deinitPythonModel(modelId.value)
  }

  return { currentTag, getModel, modelId, createModelFromFile, removeModel, deinit }
}
