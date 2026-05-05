<template>
  <div class="content">
    <TracesWrapper
      v-if="modelsIds[0] && modelsIds.length === 1"
      :artifactId="modelsIds[0]"
      :show-empty-table="false"
    />
    <Skeleton v-if="staticParamsLoading" style="height: 210px; margin-bottom: 20px"></Skeleton>
    <template v-else-if="staticParams?.length && showStaticParams">
      <StaticParameters
        v-if="modelsIds.length === 1 && staticParams[0]"
        :parameters="staticParams[0]"
      ></StaticParameters>
      <StaticParametersMultiple
        v-else
        :parameters-list="staticParams"
        :models-info="modelsInfo"
      ></StaticParametersMultiple>
    </template>

    <DynamicMetricsLoader v-if="dynamicMetricsLoading" />
    <DynamicMetrics
      v-else-if="dynamicMetricsNames"
      :metrics-names="dynamicMetricsNames"
      :models-info="modelsInfo"
    ></DynamicMetrics>

    <EvalsDatasetsList
      v-if="evalsStore.getProvider"
      :models-info="modelsInfo"
      loader-height="210px"
    ></EvalsDatasetsList>
  </div>
  <TracesDialog
    :visible="!!evalsStore.currentEvalData"
    :models-info="modelsInfo"
    @update:visible="evalsStore.resetCurrentEvalData"
  ></TracesDialog>
  <TraceDialog
    v-if="!!evalsStore.selectedTrace"
    :visible="!!evalsStore.selectedTrace"
    :tree="evalsStore.selectedTrace.tree"
    :count="evalsStore.selectedTrace.count"
    :max-span-time="evalsStore.selectedTrace.maxTime || 0"
    :min-span-time="evalsStore.selectedTrace.minTime || 0"
    :artifact-id="evalsStore.selectedTrace.artifactId"
    :trace-id="evalsStore.selectedTrace.traceId"
    @update:visible="onTraceVisibleUpdate"
  ></TraceDialog>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, onBeforeUnmount, onUnmounted, ref, toRef, watch } from 'vue'
import type {
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelsInfo,
} from './interfaces/interfaces'
import { useToast, Skeleton } from 'primevue'
import { simpleErrorToast } from './lib/primevue/data/toasts'
import { useEvalsStore } from './store/evals'
import { provideTheme } from './lib/theme/ThemeProvider'
import StaticParameters from './components/static-parameters/StaticParameters.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import StaticParametersMultiple from './components/static-parameters-multiple/StaticParametersMultiple.vue'
import TracesDialog from './components/evals/traces/TracesDialog.vue'
import TraceDialog from './components/evals/traces/trace/TraceDialog.vue'
import EvalsDatasetsList from './components/evals/EvalsDatasetsList.vue'
import TracesWrapper from './components/traces/TracesWrapper.vue'
import DynamicMetricsLoader from './components/dynamic-metrics/DynamicMetricsLoader.vue'

type Props = {
  provider: ExperimentSnapshotProvider
  modelsIds: string[]
  modelsInfo: ModelsInfo
  theme: 'light' | 'dark'
}

const props = defineProps<Props>()

provideTheme(toRef(props, 'theme'))
const toast = useToast()
const evalsStore = useEvalsStore()

let dynamicMetricsController: AbortController | null = null
let staticParamsController: AbortController | null = null

const staticParamsLoading = ref(true)
const staticParams = ref<ExperimentSnapshotStaticParams[] | null>(null)
const dynamicMetricsLoading = ref(true)
const dynamicMetricsNames = ref<string[] | null>(null)

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
  } catch {
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

function onTraceVisibleUpdate(value: boolean | undefined) {
  if (!value) {
    evalsStore.resetSelectedTrace()
  }
}

onBeforeMount(async () => {
  evalsStore.setProvider(props.provider)
  initStaticParams()
  initDynamicMetrics()
})

onBeforeUnmount(() => {
  dynamicMetricsController?.abort()
  staticParamsController?.abort()
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
</style>
