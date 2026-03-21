<template>
  <template v-if="loading">
    <Skeleton height="49px" class="mb-2"></Skeleton>
    <Skeleton height="27px" class="mb-2"></Skeleton>
    <Skeleton height="49px" class="mb-4"></Skeleton>
    <Skeleton class="h-[calc(100vh-250px)]" height="calc(100vh-250px)"></Skeleton>
  </template>

  <div v-else-if="experimentStore.experiment" class="flex flex-col flex-1">
    <DetailsBreadcrumbs
      :group-name="experimentStore.experiment.group_name ?? ''"
      :group-id="groupId"
      :experiment-name="experimentStore.experiment.name"
      :experiment-id="experimentId"
    />
    <h1 class="text-2xl font-medium pt-2 mb-2">Test experiment</h1>
    <DetailsTabs class="mb-4" />
    <RouterView />
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
      :artifact-id="String(route.params.experimentId)"
      :trace-id="evalsStore.selectedTrace.traceId"
      @update:visible="onTraceVisibleUpdate"
    ></TraceDialog>
  </div>
  <div v-else>Experiment not found...</div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed, onBeforeMount, onUnmounted, ref, toRef, watch } from 'vue'
import { useExperimentStore } from '@/store/experiment'
import { useToast, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import { useExperimentProvider } from '@/hooks/useExperimentProvider'
import {
  useEvalsStore,
  TracesDialog,
  TraceDialog,
  type ModelsInfo,
  useAnnotationsStore,
} from '@luml/experiments'
import { useThemeStore } from '@/store/theme'
import { provideTheme } from '@luml/experiments'
import DetailsBreadcrumbs from '@/components/experiments/details/DetailsBreadcrumbs.vue'
import DetailsTabs from '@/components/experiments/details/DetailsTabs.vue'

const route = useRoute()
const toast = useToast()
const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()
const { provider, createProvider, resetProvider } = useExperimentProvider()
const themeStore = useThemeStore()
const annotationsStore = useAnnotationsStore()

provideTheme(toRef(themeStore, 'theme'))

const loading = ref(true)

const groupId = computed(() => route.params.groupId as string)

const experimentId = computed(() => route.params.experimentId as string)

const modelsInfo = computed<ModelsInfo>(() => {
  if (!experimentStore.experiment) return {}
  return {
    [experimentStore.experiment.id]: {
      name: experimentStore.experiment.name,
      color: 'var(--p-primary-color)',
    },
  }
})

async function fetchData(experimentId: string) {
  try {
    loading.value = true
    await experimentStore.fetchExperiment(experimentId)
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}

function onTraceVisibleUpdate(value: boolean | undefined) {
  if (!value) {
    evalsStore.resetSelectedTrace()
  }
}

watch(experimentId, (experimentId) => fetchData(experimentId), {
  immediate: true,
})

watch(
  () => experimentStore.experiment,
  (experiment) => {
    if (experiment) createProvider([experiment])
    else resetProvider()
  },
  {
    immediate: true,
  },
)

watch(
  provider,
  (val) => {
    if (val) evalsStore.setProvider(val)
    else evalsStore.resetProvider()
  },
  {
    immediate: true,
  },
)

onBeforeMount(() => {
  annotationsStore.allowEdit()
})

onUnmounted(() => {
  experimentStore.resetExperiment()
  resetProvider()
})
</script>

<style scoped></style>
