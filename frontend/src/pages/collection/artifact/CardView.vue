<template>
  <div v-if="loading" class="loading-block">
    <ProgressSpinner></ProgressSpinner>
  </div>
  <div v-else-if="artifactsStore.currentModelMetadata && artifactsStore.currentModelTag">
    <CollectionModelCardTabular
      v-if="
        isTabular &&
        'metrics' in artifactsStore.currentModelMetadata &&
        !('model_config' in artifactsStore.currentModelMetadata)
      "
      :metrics="artifactsStore.currentModelMetadata.metrics"
      :tag="artifactsStore.currentModelTag"
    ></CollectionModelCardTabular>
    <CollectionModelCardPromptOptimization
      v-else-if="isPromptOptimization && 'edges' in artifactsStore.currentModelMetadata"
      :data="artifactsStore.currentModelMetadata"
    ></CollectionModelCardPromptOptimization>
    <CollectionModelCardForecasting
      v-else-if="isForecasting && 'model_config' in artifactsStore.currentModelMetadata"
      :metrics="artifactsStore.currentModelMetadata.metrics"
      :model-config="artifactsStore.currentModelMetadata.model_config"
      :chart="artifactsStore.currentModelMetadata.chart"
    ></CollectionModelCardForecasting>
    <div v-else class="card">
      <header class="card-header">
        <h3 class="card-title card-title--medium">Inputs and outputs</h3>
      </header>
      <div>{{ artifactsStore.currentArtifact?.manifest.producer_tags }}</div>
    </div>
  </div>
  <CollectionModelCardHtml
    v-else-if="artifactsStore.currentModelHtmlBlobUrl"
    :url="artifactsStore.currentModelHtmlBlobUrl"
  >
  </CollectionModelCardHtml>
</template>

<script setup lang="ts">
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { computed, onMounted, ref } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'
import { ProgressSpinner } from 'primevue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import type { MetaEntry } from '@fnnx-ai/common/dist/interfaces'
import type { PromptOptimizationModelMetadataPayload } from '@/lib/data-processing/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import JSZip from 'jszip'
import CollectionModelCardTabular from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardTabular.vue'
import CollectionModelCardPromptOptimization from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardPromptOptimization.vue'
import CollectionModelCardForecasting from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardForecasting.vue'
import CollectionModelCardHtml from '@/components/orbits/tabs/registry/collection/artifact/card/CollectionModelCardHtml.vue'

const artifactsStore = useArtifactsStore()

const loading = ref(false)

const isTabular = computed(
  () => artifactsStore.currentModelTag && FnnxService.isTabularTag(artifactsStore.currentModelTag),
)
const isPromptOptimization = computed(
  () =>
    artifactsStore.currentModelTag &&
    FnnxService.isPromptOptimizationTag(artifactsStore.currentModelTag),
)
const isForecasting = computed(
  () =>
    artifactsStore.currentModelTag && FnnxService.isForecastingTag(artifactsStore.currentModelTag),
)

function setTabularMetadata(file: MetaEntry[]) {
  const metrics = FnnxService.getTabularMetrics(file)
  artifactsStore.setCurrentModelMetadata({ metrics })
}

function setPromptOptimizationMetadata(file: MetaEntry[]) {
  const data = FnnxService.getPromptOptimizationData(file) as PromptOptimizationModelMetadataPayload
  artifactsStore.setCurrentModelMetadata(data)
}

function setForecastingMetadata(file: MetaEntry[]) {
  const data = FnnxService.getForecastingData(file)
  if (!data) return
  const chart = FnnxService.getForecastingChart(file)
  artifactsStore.setCurrentModelMetadata({ ...data, chart })
}

async function setHtmlData(model: ModelArtifact) {
  const htmlArchiveName = FnnxService.findHtmlCard(model.file_index)
  if (!htmlArchiveName) return
  const url = await artifactsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const arrayBuffer = await modelDownloader.getFileFromBucket<ArrayBuffer>(
    model.file_index,
    htmlArchiveName,
    true,
  )
  const zip = await JSZip.loadAsync(arrayBuffer)
  const rawFile = await zip.file(Object.keys(zip.files)[0])?.async('arraybuffer')
  if (!rawFile) throw new Error('File not found')
  const decoder = new TextDecoder('utf-8')
  let fileString = decoder.decode(rawFile)
  if (!fileString.includes('<meta charset=')) {
    fileString = fileString.replace(
      /<head>/i,
      `<head>
        <meta charset="UTF-8">`,
    )
  }
  const blob = new Blob([fileString], { type: 'text/html' })
  const blobUrl = URL.createObjectURL(blob)
  artifactsStore.setCurrentModelHtmlBlobUrl(blobUrl)
}

async function setLumlMetadata(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM, model: ModelArtifact) {
  const metadataFileName = FnnxService.getModelMetadataFileName(model.file_index)
  if (!metadataFileName) return
  artifactsStore.setCurrentModelTag(tag)
  const url = await artifactsStore.getDownloadUrl(model.id)
  const modelDownloader = new ModelDownloader(url)
  const file = await modelDownloader.getFileFromBucket<MetaEntry[]>(
    model.file_index,
    metadataFileName,
  )
  if (FnnxService.isTabularTag(tag)) {
    setTabularMetadata(file as MetaEntry[])
  } else if (FnnxService.isPromptOptimizationTag(tag)) {
    setPromptOptimizationMetadata(file as MetaEntry[])
  } else if (FnnxService.isForecastingTag(tag)) {
    setForecastingMetadata(file as MetaEntry[])
  }
}

async function setMetadata() {
  const model = artifactsStore.currentArtifact
  if (!model) throw new Error('Current model does not exist')
  const currentTag = FnnxService.getTypeTag(model.manifest)
  if (currentTag) {
    await setLumlMetadata(currentTag, model)
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
  if (artifactsStore.currentModelMetadata || artifactsStore.currentModelHtmlBlobUrl) return
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
