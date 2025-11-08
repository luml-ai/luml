<template>
  <div class="wrapper">
    <header class="header">
      <h1 class="title">Runtime</h1>
      <d-button label="finish" @click="$router.push({ name: 'home' })" />
    </header>
    <div class="board">
      <div class="card">
        <h2 class="card-title">
          Model perfomance
          <Info
            color="var(--p-icon-muted-color)"
            width="20"
            height="20"
            v-tooltip.bottom="
              `Track your model's effectiveness through performance metrics. Higher scores indicate better predictions and generalization to new data`
            "
          />
        </h2>
        <model-performance :metrics="metricCardsData" :total-score="totalScore" />
      </div>
      <div class="card" :class="{ 'card-predict-manual': predictType === 'Manual' }">
        <h2 class="card-title">Predict</h2>
        <div class="card-sub-title">
          Get predictions by entering data manually or uploading a dataset
        </div>
        <div class="predict-wrapper">
          <select-button v-model="predictType" :options="['Manual', 'Upload file']" />
          <predict-manual
            v-if="predictType === 'Manual'"
            :input-names="inputNames"
            :predict-callback="predict"
          />
          <predict-file :predict-callback="predict" v-else />
        </div>
      </div>
      <div class="card">
        <h2 class="card-title">Top {{ features.length }} features</h2>
        <model-top-features :features="features" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { type TabularMetrics } from '@/lib/data-processing/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { Info } from 'lucide-vue-next'
import { SelectButton } from 'primevue'
import PredictManual from './PredictManual.vue'
import PredictFile from './PredictFile.vue'
import ModelPerformance from './ModelPerformance.vue'
import ModelTopFeatures from './ModelTopFeatures.vue'
import { getMetricsCards } from '@/helpers/helpers'
import { Model } from '@fnnx/web'
import { ArrayDType, NDArray } from '@fnnx/common'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import '@/lib/onnx/onnx'

type Props = {
  model: Model
  currentTag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM
}

const props = defineProps<Props>()

const predictType = ref<'Manual' | 'Upload file'>('Manual')
const metrics = ref<TabularMetrics | null>(null)

const inputNames = computed(() => {
  if (!props.model) return []
  const manifest = (props.model as any).manifest
  return manifest.inputs.map((input: any) => input.name)
})
const features = computed(() => {
  if (!metrics.value) return []
  return FnnxService.getTop5TabularFeatures(metrics.value)
})
const totalScore = computed(() => {
  if (!metrics.value) return 0
  return FnnxService.getTabularTotalScore(metrics.value)
})
const testMetrics = computed(() => {
  if (!metrics.value || !props.currentTag) return []
  return FnnxService.prepareTabularMetrics(
    metrics.value.performance.eval_cv || metrics.value.performance.eval_holdout!,
    props.currentTag,
  )
})
const trainMetrics = computed(() => {
  if (!metrics.value || !props.currentTag) return []
  return FnnxService.prepareTabularMetrics(metrics.value.performance.train, props.currentTag)
})
const metricCardsData = computed(() =>
  props.currentTag ? getMetricsCards(testMetrics.value, trainMetrics.value, props.currentTag) : [],
)

async function predict(values: Record<string, (string | number)[]>) {
  const inputs = prepareData(values)
  if (!Object.keys(inputs).length)
    throw new Error('Failed to convert predict data. The data is incorrect.')
  const result = await props.model.compute(inputs, {})
  if (!result?.y_pred.data) throw new Error('Predict Failed')
  return result.y_pred.data
}
function prepareData(values: Record<string, (string | number)[]>) {
  const manifest = props.model.getManifest()
  const data: Record<string, any> = {}
  for (const key in values) {
    const valueInfo = manifest.inputs.find((input: any) => input.name === key)
    if (!valueInfo) throw new Error('Incorrect data')
    const inputType = extractType(valueInfo.dtype)
    if (inputType) {
      data[key] = new NDArray([values[key].length, 1], values[key], inputType)
    }
  }
  return data
}
function extractType(string: string): ArrayDType | null {
  const match = string.match(/Array\[(.*)\]/)
  return match ? (match[1] as ArrayDType) : null
}

onBeforeMount(() => {
  metrics.value = FnnxService.getTabularMetrics(props.model.getMetadata())
})
</script>

<style scoped>
.wrapper {
  padding-top: 30px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.board {
  display: grid;
  grid-template-columns: 478px 1fr;
  gap: 24px;
}
.card {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  padding: 24px;
  box-shadow: var(--card-shadow);
}
.card-predict-manual {
  grid-row: span 2;
}
.card-title {
  font-size: 20px;
  font-weight: 400;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-sub-title {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.predict-wrapper {
  padding-top: 28px;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1280px) {
  .board {
    grid-template-columns: 1fr;
  }
  .card:nth-child(2) {
    order: 3;
  }
}
</style>
