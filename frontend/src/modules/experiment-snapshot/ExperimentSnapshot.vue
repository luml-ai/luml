<template>
  <div class="content">
    <Button v-if="showTracesButton" severity="secondary" @click="showTraces">
      <ListTree :size="16" />
      Traces
    </Button>
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
  <TracesInfoDialog
    :visible="!!tracesData"
    :data="tracesData || []"
    @update:visible="onTracesInfoVisibleUpdate"
    @select="selectTrace"
  ></TracesInfoDialog>
  <TraceDialog
    v-if="!!evalsStore.selectedTrace"
    :visible="!!evalsStore.selectedTrace"
    :tree="evalsStore.selectedTrace.tree"
    :count="evalsStore.selectedTrace.count"
    :max-span-time="evalsStore.selectedTrace.maxTime || 0"
    :min-span-time="evalsStore.selectedTrace.minTime || 0"
    @update:visible="onTraceVisibleUpdate"
  ></TraceDialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue'
import type {
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelsInfo,
  BaseTraceInfo,
} from './interfaces/interfaces'
import { useToast, Skeleton, Button } from 'primevue'
import { simpleErrorToast } from './lib/primevue/data/toasts'
import { useEvalsStore } from './store/evals'
import { ListTree } from 'lucide-vue-next'
import StaticParameters from './components/static-parameters/StaticParameters.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import EvalsCard from './components/evals/EvalsCard.vue'
import StaticParametersMultiple from './components/static-parameters-multiple/StaticParametersMultiple.vue'
import TracesDialog from './components/evals/traces/TracesDialog.vue'
import TracesInfoDialog from './components/evals/traces/TracesInfoDialog.vue'
import TraceDialog from './components/evals/traces/trace/TraceDialog.vue'

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
const tracesIds = ref<string[] | null>(null)
const tracesLoading = ref(false)
const tracesData = ref<BaseTraceInfo[] | null>(null)

const showStaticParams = computed(() => {
  if (!staticParams.value) return false
  return staticParams.value.find((params) => Object.keys(params).find((key) => key !== 'modelId'))
})

const showTracesButton = computed(() => {
  return props.modelsIds.length === 1 && tracesIds.value?.length
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

async function showTraces() {
  tracesLoading.value = true
  try {
    tracesData.value = await getTracesData()
  } catch {
    toast.add(simpleErrorToast('Failed to load traces'))
  } finally {
    tracesLoading.value = false
  }
}

async function getTracesData() {
  if (!tracesIds.value) return []
  const promises = tracesIds.value.map(async (traceId) => {
    return evalsStore.getTraceSpansTree(props.modelsIds[0], traceId)
  })
  return Promise.all(promises)
}

function onTracesInfoVisibleUpdate(value: boolean | undefined) {
  if (!value) {
    tracesData.value = null
  }
}

function selectTrace(trace: BaseTraceInfo) {
  evalsStore.setSelectedTrace(trace)
}

function onTraceVisibleUpdate(value: boolean | undefined) {
  if (!value) {
    evalsStore.resetSelectedTrace()
  }
}

async function getUniqueTracesIds(modelId: string) {
  tracesLoading.value = true
  try {
    tracesIds.value = await evalsStore.getUniqueTraceIds(modelId)
  } catch (error: any) {
    console.error(error)
  } finally {
    tracesLoading.value = false
  }
}

onMounted(async () => {
  evalsStore.setProvider(props.provider)
  if (props.modelsIds.length === 1) {
    getUniqueTracesIds(props.modelsIds[0])
  }
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
