<template>
  <div class="content">
    <template v-if="staticParams?.length && showStaticParams">
      <StaticParameters
        v-if="modelsIds.length === 1"
        :parameters="staticParams[0]"
      ></StaticParameters>
      <StaticParametersMultiple
        v-else
        :parameters-list="staticParams"
        :models-info="modelsInfo"
      ></StaticParametersMultiple>
    </template>
    <DynamicMetrics
      v-if="dynamicMetrics"
      :metrics-list="dynamicMetrics"
      :models-info="modelsInfo"
    ></DynamicMetrics>
    <div v-if="evalsStore.evals && Object.keys(evalsStore.evals)" class="evals-list">
      <EvalsCard
        v-for="item of evalsStore.evals"
        :data="item"
        :models-info="modelsInfo"
      ></EvalsCard>
    </div>
  </div>
  <TracesDialog
    :visible="!!evalsStore.currentEvalData"
    :models-info="modelsInfo"
    @update:visible="evalsStore.resetCurrentEvalData"
  ></TracesDialog>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type {
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelsInfo,
} from './interfaces/interfaces'
import StaticParameters from './components/static-parameters/StaticParameters.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import EvalsCard from './components/evals/EvalsCard.vue'
import { useToast } from 'primevue'
import { simpleErrorToast } from './lib/primevue/data/toasts'
import StaticParametersMultiple from './components/static-parameters-multiple/StaticParametersMultiple.vue'
import TracesDialog from './components/evals/traces/TracesDialog.vue'
import { useEvalsStore } from './store/evals'

type Props = {
  provider: ExperimentSnapshotProvider
  modelsIds: number[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const toast = useToast()
const evalsStore = useEvalsStore()

const staticParams = ref<ExperimentSnapshotStaticParams[] | null>(null)
const dynamicMetrics = ref<ExperimentSnapshotDynamicMetrics[] | null>()

const showStaticParams = computed(() => {
  if (!staticParams.value) return false
  return staticParams.value.find((params) => Object.keys(params).find((key) => key !== 'modelId'))
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
    evalsStore.setEvals()
  } catch (error: any) {
    toast.add(simpleErrorToast(error.message))
  }
}

onMounted(async () => {
  evalsStore.setProvider(props.provider)
  setStaticParams()
  setDynamicMetrics()
  setEvals()
})

onUnmounted(() => {
  evalsStore.reset()
  document.documentElement.classList.remove('lock')
})

watch(
  () => !!evalsStore.currentEvalData,
  (val) => {
    if (val) {
      document.documentElement.classList.add('lock')
    } else {
      document.documentElement.classList.remove('lock')
    }
  },
)
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
