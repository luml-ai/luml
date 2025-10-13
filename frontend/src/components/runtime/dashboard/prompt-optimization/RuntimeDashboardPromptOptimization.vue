<template>
  <div class="body">
    <RuntimeDashboardPromptOptimizationHeader
      :provider-id="providerId"
    ></RuntimeDashboardPromptOptimizationHeader>
    <div class="content-area">
      <PresentationArea
        v-if="initialNodes && initialEdges"
        :initial-nodes="initialNodes"
        :initial-edges="initialEdges"
      ></PresentationArea>
      <Skeleton v-else style="height: 100%"></Skeleton>
      <div class="predict-card">
        <h2 class="predict-card-title">Predict</h2>
        <RuntimeDashboardPromptOptimizationPredict
          :manual-fields="fields"
          :model-id="props.modelId"
          :dynamic-attributes="dynamicAttributes"
          :provider-connected="providerConnected"
        ></RuntimeDashboardPromptOptimizationPredict>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Model } from '@fnnx/web'
import type { PromptNode } from '@/components/express-tasks/prompt-fusion/interfaces'
import type { Edge } from '@vue-flow/core'
import type { MetaEntry } from '@fnnx/common/dist/interfaces'
import {
  ProviderAttributesMap,
  ProviderDynamicAttributesTagsEnum,
  ProvidersEnum,
  type PayloadData,
} from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { computed, onBeforeMount, onMounted, onUnmounted, ref } from 'vue'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { Skeleton } from 'primevue'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import RuntimeDashboardPromptOptimizationHeader from './RuntimeDashboardPromptOptimizationHeader.vue'
import PresentationArea from './PresentationArea.vue'
import RuntimeDashboardPromptOptimizationPredict from './RuntimeDashboardPromptOptimizationPredict.vue'
import { mock } from 'mock-json-schema'

type Props = {
  model: Model
  modelId: string
}

interface MetadataItem extends MetaEntry {
  provider: ProvidersEnum
}

const props = defineProps<Props>()

const providerConnected = ref(false)
const initialNodes = ref<PromptNode[] | null>(null)
const initialEdges = ref<Edge[] | null>(null)
const dynamicAttributes = ref<Record<string, string | number>>({})

const providerId = computed(() => {
  const metadata = props.model.getMetadata()
  const info = metadata[0] as MetadataItem
  return Object.values(ProvidersEnum).find(
    (item) => item.toLowerCase() === info.provider,
  ) as ProvidersEnum
})
const fields = computed(() => {
  const dtypes = props.model.getDtypes() as Record<string, any>
  const schema = dtypes['ext::in']
  if (!schema) return []
  const sample = mock(schema)
  return Object.keys(sample)
})

function onSettingsChange() {
  providerConnected.value = !!promptFusionService.availableModels.find(
    (model) => model.providerId === providerId.value,
  )
  setDynamicAttributes()
}

function setDynamicAttributes() {
  const manifest = props.model.getManifest()
  const dynamicAttributesList = manifest.dynamic_attributes
    .map((attribute) => {
      const tag = attribute.tags?.find(
        (tag): tag is keyof typeof ProviderDynamicAttributesTagsEnum =>
          tag in ProviderDynamicAttributesTagsEnum,
      )
      return tag ? ProviderDynamicAttributesTagsEnum[tag] : null
    })
    .filter((attribute) => !!attribute)
  const providerSettings = LocalStorageService.get('dataforce.providersSettings')?.[
    providerId.value
  ]
  const entries = dynamicAttributesList.map((attribute) => {
    const value = providerSettings?.[attribute] || ''
    return [ProviderAttributesMap[attribute], value]
  })
  dynamicAttributes.value = Object.fromEntries(entries)
}

onBeforeMount(() => {
  const metadata = props.model.getMetadata()
  const payload = metadata[0].payload
  if (!payload.nodes || !payload.edges) return
  const flow = promptFusionService.createFlowFromMetadata(payload as PayloadData)
  initialNodes.value = flow.nodes
  initialEdges.value = flow.edges
})

onMounted(() => {
  promptFusionService.on('CHANGE_AVAILABLE_MODELS', onSettingsChange)
  onSettingsChange()
})

onUnmounted(() => {
  promptFusionService.off('CHANGE_AVAILABLE_MODELS', onSettingsChange)
})
</script>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 32px;
}

.content-area {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 24px;
  overflow: hidden;
}

.predict-card {
  align-self: flex-start;
  padding: 24px;
  border-radius: var(--p-border-radius-lg);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  max-height: 100%;
  overflow-y: auto;
}

.predict-card-title {
  font-size: 20px;
  margin-bottom: 12px;
}

@media (min-width: 1201px) {
  .body {
    height: calc(100vh - 130px);
  }
}

@media (max-width: 1200px) {
  .content-area {
    display: flex;
    flex-direction: column;
  }

  .presentation {
    height: 600px;
  }

  .predict-card {
    align-self: stretch;
  }
}
</style>
