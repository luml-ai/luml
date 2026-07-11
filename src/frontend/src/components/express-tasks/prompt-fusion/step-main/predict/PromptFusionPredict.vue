<template>
  <d-dialog
    :visible="visible"
    modal
    header="Predict"
    :style="{ width: '31.25rem' }"
    @update:visible="promptFusionService.togglePredict()"
  >
    <predict-content
      v-if="modelId && fields"
      :manual-fields="fields"
      :model-id="modelId"
      task="prompt_optimization"
    />
    <h3 v-else>Predict not available...</h3>
  </d-dialog>
</template>

<script setup lang="ts">
import { onBeforeMount, onBeforeUnmount, ref } from 'vue'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import PredictContent from '@/components/predict/index.vue'

const visible = ref(false)
const modelId = ref(promptFusionService.modelId)
const fields = ref<string[] | null>(null)

function onChangePredictVisible(value: boolean) {
  visible.value = value
}
function onChangeModelId(id: string) {
  modelId.value = id
}
function onChangePredictionFields(data: string[] | null) {
  fields.value = data
}

onBeforeMount(() => {
  promptFusionService.on('CHANGE_PREDICT_VISIBLE', onChangePredictVisible)
  promptFusionService.on('CHANGE_MODEL_ID', onChangeModelId)
  promptFusionService.on('CHANGE_PREDICTION_FIELDS', onChangePredictionFields)
})
onBeforeUnmount(() => {
  promptFusionService.off('CHANGE_PREDICT_VISIBLE', onChangePredictVisible)
  promptFusionService.off('CHANGE_MODEL_ID', onChangeModelId)
  promptFusionService.off('CHANGE_PREDICTION_FIELDS', onChangePredictionFields)
})
</script>

<style scoped></style>
