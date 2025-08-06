<template>
  <div v-if="currentModel">
    <div class="title">Model details</div>
    <CollectionModelTabs></CollectionModelTabs>
    <div class="view-wrapper">
      <RouterView></RouterView>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useModelsStore } from '@/stores/models'
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ModelDownloader } from '@/lib/bucket-service'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import CollectionModelTabs from '@/components/orbits/tabs/registry/collection/model/CollectionModelTabs.vue'
import JSZip from 'jszip'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'

const modelsStore = useModelsStore()
const route = useRoute()

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})

function setTabularMetadata(file: any) {
  const metrics = FnnxService.getTabularMetrics(file)
  modelsStore.setCurrentModelMetadata({ metrics })
}

function setOptimizationMetadata(file: any) {
  const data = FnnxService.getPromptOptimizationData(file)
  modelsStore.setCurrentModelMetadata(data)
}

async function setHtmlData(model: MlModel) {
  const htmlArchiveName = getHtmlArchiveName(Object.keys(model.file_index))
  if (!htmlArchiveName) return
  const url = await modelsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const arrayBuffer: ArrayBuffer = await modelDownloader.getFileFromBucket(
    model,
    htmlArchiveName,
    true,
  )
  const zip = await JSZip.loadAsync(arrayBuffer)
  const fileString = await zip.file(Object.keys(zip.files)[0])?.async('string')
  if (!fileString) throw new Error('File not found')
  const blob = new Blob([fileString], { type: 'text/html' })
  const blobUrl = URL.createObjectURL(blob)
  modelsStore.setCurrentModelHtmlBlobUrl(blobUrl)
}

function getHtmlArchiveName(files: string[]) {
  return files.find((file) => file.endsWith('.html.zip'))
}

function getModelMetadataFileName(model: MlModel) {
  if (model.file_index['meta.json']) return 'meta.json'
  return null
}

async function setDataforceMetadata(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM, model: MlModel) {
  const metadataFileName = getModelMetadataFileName(model)
  if (!metadataFileName) return
  modelsStore.setCurrentModelTag(tag)
  const url = await modelsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const file = await modelDownloader.getFileFromBucket(model, metadataFileName)
  if (FnnxService.isTabularTag(tag)) {
    setTabularMetadata(file)
  } else if (FnnxService.isOptimizationTag(tag)) {
    setOptimizationMetadata(file)
  }
}

async function setMetadata() {
  const model = currentModel.value
  if (!model) throw new Error('Current model not exist')
  const currentTag = FnnxService.getTypeTag(model.manifest)
  if (currentTag) {
    await setDataforceMetadata(currentTag, model)
  } else {
    await setHtmlData(model)
  }
}

onMounted(async () => {
  try {
    await setMetadata()
  } catch (e) {
    console.error(e)
  }
})

onUnmounted(() => {
  modelsStore.resetCurrentModelTag()
  modelsStore.resetCurrentModelMetadata()
})
</script>

<style scoped>
.title {
  margin-bottom: 20px;
}

.view-wrapper {
  padding-top: 20px;
}
</style>
