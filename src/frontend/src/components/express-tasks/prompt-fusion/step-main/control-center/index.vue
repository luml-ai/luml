<template>
  <div class="content">
    <providers-component />
    <optimization-component :disabled="optimizationDisabled" />
    <SplitButton
      severity="secondary"
      :model="EXPORT_ITEMS"
      :disabled="!isPredictAvailable"
      @click="onDownloadClick"
    >
      <template #icon>
        <cloud-download :size="14" />
      </template>
    </SplitButton>
    <d-button
      v-tooltip.bottom="'Run the model'"
      severity="secondary"
      :disabled="!isPredictAvailable"
      @click="promptFusionService.togglePredict()"
    >
      <template #icon>
        <play :size="14" />
      </template>
    </d-button>
  </div>
  <ModelUpload
    v-if="promptFusionService.modelBlob && !!organizationStore.currentOrganization"
    v-model:visible="modelUploadVisible"
    current-task="prompt_optimization"
    :model-blob="promptFusionService.modelBlob"
  ></ModelUpload>
</template>

<script setup lang="ts">
import { onBeforeMount, onBeforeUnmount, ref } from 'vue'
import { Play, CloudDownload } from 'lucide-vue-next'
import ProvidersComponent from '@/components/express-tasks/prompt-fusion/step-main/control-center/providers/index.vue'
import OptimizationComponent from '@/components/express-tasks/prompt-fusion/step-main/control-center/optimization/index.vue'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import ModelUpload from '@/components/model-upload/ModelUpload.vue'
import { SplitButton } from 'primevue'
import { useOrganizationStore } from '@/stores/organization'

const EXPORT_ITEMS = [
  {
    label: 'Upload to Registry',
    command: () => {
      modelUploadVisible.value = true
    },
    disabled: () => !organizationStore.currentOrganization,
  },
  {
    label: 'Download model',
    command: () => {
      onDownloadClick()
    },
  },
]

const organizationStore = useOrganizationStore()

const optimizationDisabled = ref(true)
const isPredictAvailable = ref(false)
const modelUploadVisible = ref(false)

function setOptimizationState() {
  promptFusionService.changeAvailableModels()
  optimizationDisabled.value = !promptFusionService.getConnectedProviders().length
}
function onChangeModelId(modelId: string) {
  isPredictAvailable.value = !!modelId
}
function onDownloadClick() {
  promptFusionService.downloadModel()
  AnalyticsService.track(AnalyticsTrackKeysEnum.download, { task: 'prompt_optimization' })
}

onBeforeMount(() => {
  setOptimizationState()
  promptFusionService.on('CLOSE_PROVIDER_SETTINGS', setOptimizationState)
  promptFusionService.on('CHANGE_MODEL_ID', onChangeModelId)
})
onBeforeUnmount(() => {
  promptFusionService.off('CLOSE_PROVIDER_SETTINGS', setOptimizationState)
  promptFusionService.off('CHANGE_MODEL_ID', onChangeModelId)
})
</script>

<style scoped>
.content {
  position: absolute;
  top: 16px;
  right: 18px;
  z-index: 2;
  display: flex;
  gap: 8px;
}
.other-buttons {
  padding: 0 2px;
  display: flex;
  gap: 4px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}
</style>
