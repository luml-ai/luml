import { Model } from '@fnnx/web'
import { computed, ref } from 'vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService';


export const useFnnxModel = () => {
  const model = ref<Model | null>(null)
  const currentTag = ref<FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null>(null)

  const getModel = computed(() => model.value)

  async function createModelFromFile(file: File) {
    if (!file.name.endsWith('.dfs')) throw new Error('Incorrect file format')
    const buffer = await file.arrayBuffer()
    model.value = await Model.fromBuffer(buffer)
    currentTag.value = FnnxService.getTypeTag(model.value.getManifest())
    await model.value.warmup()
  }
  function removeModel() {
    model.value = null
  }

  return { currentTag, getModel, createModelFromFile, removeModel }
}
