<template>
  <div class="content">
    <template v-if="staticParams?.length">
      <StaticParameters
        v-if="modelsIds.length === 1"
        :parameters="staticParams[0]"
      ></StaticParameters>
      <StaticParametersMultiple
        v-else
        :parameters-list="staticParams"
        :models-ids="modelsIds"
      ></StaticParametersMultiple>
    </template>
    <DynamicMetrics
      v-if="dynamicMetrics"
      :metrics-list="dynamicMetrics"
      :models-names="modelsNames"
    ></DynamicMetrics>
    <div v-if="evals && Object.keys(evals)" class="evals-list">
      <EvalsCard v-for="item of evals" :data="item" :models-info="modelsInfo"></EvalsCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type {
  EvalsDatasets,
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelsInfo,
} from './interfaces/interfaces'
import StaticParameters from './components/static-parameters/StaticParameters.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import EvalsCard from './components/evals/EvalsCard.vue'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import StaticParametersMultiple from './components/static-parameters-multiple/StaticParametersMultiple.vue'
import { getModelColorByIndex } from './helpers/helpers'

type Props = {
  provider: ExperimentSnapshotProvider
  modelsIds: number[]
  modelsNames: Record<string, string>
}

const props = defineProps<Props>()

const toast = useToast()

const staticParams = ref<ExperimentSnapshotStaticParams[] | null>(null)
const dynamicMetrics = ref<ExperimentSnapshotDynamicMetrics[] | null>()
const evals = ref<EvalsDatasets | null>(null)

const modelsInfo = computed(() => {
  return props.modelsIds.reduce((acc: ModelsInfo, modelId, index) => {
    const name = props.modelsNames[modelId]
    const color = getModelColorByIndex(index)
    acc[modelId] = { name, color }
    return acc
  }, {})
})

async function setStaticParams() {
  try {
    staticParams.value = await props.provider.getStaticParamsList()
  } catch (error) {
    toast.add(simpleErrorToast('Failed to load static params'))
  }
}

async function setDynamicMetrics() {
  try {
    dynamicMetrics.value = await props.provider.getDynamicMetricsList()
  } catch (error) {
    toast.add(simpleErrorToast('Failed to load dynamic metrics'))
  }
}

async function setEvals() {
  try {
    evals.value = await props.provider.getEvalsList()
  } catch (error: any) {
    toast.add(simpleErrorToast(error.message))
  }
}

onMounted(async () => {
  setStaticParams()
  setDynamicMetrics()
  setEvals()
})
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.evals-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
