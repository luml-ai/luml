<template>
  <div class="content">
    <Skeleton v-if="staticParamsLoading" style="height: 210px; margin-bottom: 20px"></Skeleton>
    <template v-else-if="staticParams?.length && showStaticParams">
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

    <div
      v-if="dynamicMetricsLoading"
      style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px"
    >
      <Skeleton style="height: 300px; width: 100%"></Skeleton>
      <Skeleton style="height: 300px; width: 100%"></Skeleton>
    </div>
    <DynamicMetrics
      v-else-if="dynamicMetricsNames"
      :metrics-names="dynamicMetricsNames"
      :provider="props.provider"
      :models-info="modelsInfo"
    ></DynamicMetrics>

    <div v-if="evalsLoading" style="height: 210px; margin-bottom: 20px"></div>
    <div v-else-if="evalsStore.evals && Object.keys(evalsStore.evals)" class="evals-list">
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
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue'
import type {
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelsInfo,
} from './interfaces/interfaces'
import { useToast, Skeleton } from 'primevue'
import { simpleErrorToast } from './lib/primevue/data/toasts'
import { useEvalsStore } from './store/evals'
import StaticParameters from './components/static-parameters/StaticParameters.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import EvalsCard from './components/evals/EvalsCard.vue'
import StaticParametersMultiple from './components/static-parameters-multiple/StaticParametersMultiple.vue'
import TracesDialog from './components/evals/traces/TracesDialog.vue'

type Props = {
  provider: ExperimentSnapshotProvider
  modelsIds: string[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const toast = useToast()
const evalsStore = useEvalsStore()

let dynamicMetricsController: AbortController | null = null
let staticParamsController: AbortController | null = null
let evalsController: AbortController | null = null

const staticParamsLoading = ref(true)
const staticParams = ref<ExperimentSnapshotStaticParams[] | null>(null)
const dynamicMetricsLoading = ref(true)
const dynamicMetricsNames = ref<string[] | null>(null)
const evalsLoading = ref(true)

const showStaticParams = computed(() => {
  if (!staticParams.value) return false
  return staticParams.value.find((params) => Object.keys(params).find((key) => key !== 'modelId'))
})

async function initStaticParams() {
  staticParamsController?.abort()
  staticParamsController = new AbortController()
  try {
    staticParamsLoading.value = true
    staticParams.value = await props.provider.getStaticParamsList(staticParamsController.signal)
  } catch (error) {
    toast.add(simpleErrorToast('Failed to load static params'))
  } finally {
    staticParamsLoading.value = false
  }
}

async function initDynamicMetrics() {
  dynamicMetricsController?.abort()
  dynamicMetricsController = new AbortController()
  try {
    dynamicMetricsLoading.value = true
    dynamicMetricsNames.value = await props.provider.getDynamicMetricsNames(
      dynamicMetricsController.signal,
    )
    dynamicMetricsLoading.value = false
  } catch (error) {
    if (error instanceof DOMException) return
    toast.add(simpleErrorToast('Failed to load dynamic metrics'))
  } finally {
    dynamicMetricsLoading.value = false
  }
}

async function initEvals() {
  evalsController?.abort()
  evalsController = new AbortController()
  try {
    evalsLoading.value = true
    evalsStore.setEvals(evalsController.signal)
  } catch (error: any) {
    toast.add(simpleErrorToast(error.message))
  } finally {
    evalsLoading.value = false
  }
}

onMounted(async () => {
  evalsStore.setProvider(props.provider)
  initStaticParams()
  initDynamicMetrics()
  initEvals()
})

onBeforeUnmount(() => {
  dynamicMetricsController?.abort()
  staticParamsController?.abort()
  evalsController?.abort()
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
