<template>
  <div v-if="loading" class="loading-block">
    <ProgressSpinner></ProgressSpinner>
  </div>
  <div v-else-if="modelsStore.currentModelMetadata && modelsStore.currentModelTag">
    <CollectionModelCardTabular
      v-if="isTabular && 'metrics' in modelsStore.currentModelMetadata"
      :metrics="modelsStore.currentModelMetadata.metrics"
      :tag="modelsStore.currentModelTag"
    ></CollectionModelCardTabular>
    <CollectionModelCardPromptOptimization
      v-else-if="isPromptOptimization && 'edges' in modelsStore.currentModelMetadata"
      :data="modelsStore.currentModelMetadata"
    ></CollectionModelCardPromptOptimization>
    <div v-else class="card">
      <header class="card-header">
        <h3 class="card-title card-title--medium">Inputs and outputs</h3>
      </header>
      <div>{{ currentModel?.manifest.producer_tags }}</div>
    </div>
  </div>
  <CollectionModelCardHtml
    v-else-if="modelsStore.currentModelHtmlBlobUrl"
    :url="modelsStore.currentModelHtmlBlobUrl"
  >
  </CollectionModelCardHtml>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { ProgressSpinner } from 'primevue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import CollectionModelCardTabular from '@/components/orbits/tabs/registry/collection/model/card/CollectionModelCardTabular.vue'
import CollectionModelCardPromptOptimization from '@/components/orbits/tabs/registry/collection/model/card/CollectionModelCardPromptOptimization.vue'
import CollectionModelCardHtml from '@/components/orbits/tabs/registry/collection/model/card/CollectionModelCardHtml.vue'
import { ModelDownloader } from '@/lib/bucket-service'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import JSZip from 'jszip'

const modelsStore = useModelsStore()
const route = useRoute()

const loading = ref(false)

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === +route.params.modelId)
})
const isTabular = computed(
  () => modelsStore.currentModelTag && FnnxService.isTabularTag(modelsStore.currentModelTag),
)
const isPromptOptimization = computed(
  () =>
    modelsStore.currentModelTag && FnnxService.isPromptOptimizationTag(modelsStore.currentModelTag),
)

function setTabularMetadata(file: any) {
  const metrics = FnnxService.getTabularMetrics(file)
  modelsStore.setCurrentModelMetadata({ metrics })
}

function setPromptOptimizationMetadata(file: any) {
  const data = FnnxService.getPromptOptimizationData(file)
  modelsStore.setCurrentModelMetadata(data)
}

async function setHtmlData(model: MlModel) {
  const htmlArchiveName = FnnxService.findHtmlCard(model.file_index)
  if (!htmlArchiveName) return
  const url = await modelsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const arrayBuffer: ArrayBuffer = await modelDownloader.getFileFromBucket(
    model.file_index,
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

async function setDataforceMetadata(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM, model: MlModel) {
  const metadataFileName = FnnxService.getModelMetadataFileName(model.file_index)
  if (!metadataFileName) return
  modelsStore.setCurrentModelTag(tag)
  const url = await modelsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const file = await modelDownloader.getFileFromBucket(model.file_index, metadataFileName)
  if (FnnxService.isTabularTag(tag)) {
    setTabularMetadata(file)
  } else if (FnnxService.isPromptOptimizationTag(tag)) {
    setPromptOptimizationMetadata(file)
  }
}

async function setMetadata() {
  const model = currentModel.value
  if (!model) throw new Error('Current model does not exist')
  const currentTag = FnnxService.getTypeTag(model.manifest)
  if (currentTag) {
    await setDataforceMetadata(currentTag, model)
  } else {
    await setHtmlData(model)
  }
}

async function init() {
  try {
    loading.value = true
    await setMetadata()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (modelsStore.currentModelMetadata || modelsStore.currentModelHtmlBlobUrl) return
  init()
})
</script>

<style scoped>
.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.card-title--medium {
  font-weight: 500;
}

.info-icon {
  color: var(--p-icon-muted-color);
}

.loading-block {
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
