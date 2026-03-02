<template>
  <template v-if="loading">
    <Skeleton height="49px" class="mb-2"></Skeleton>
    <Skeleton height="27px" class="mb-2"></Skeleton>
    <Skeleton height="49px" class="mb-4"></Skeleton>
    <Skeleton class="h-[calc(100vh-250px)]" height="calc(100vh-250px)"></Skeleton>
  </template>

  <div v-else-if="groupData && experimentStore.experiment">
    <DetailsBreadcrumbs
      :group-name="groupData.name"
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
      @update:visible="onTraceVisibleUpdate"
    ></TraceDialog>
  </div>
  <div v-else>Experiment not found...</div>
</template>

<script setup lang="ts">
import type { Group } from '@/store/groups/groups.interface'
import { useRoute } from 'vue-router'
import { computed, onUnmounted, ref, toRef, watch } from 'vue'
import { apiService } from '@/api/api.service'
import { useExperimentStore } from '@/store/experiment'
import { useToast, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import { useExperimentProvider } from '@/hooks/useExperimentProvider'
import { useEvalsStore, TracesDialog, TraceDialog, type ModelsInfo } from '@luml/experiments'
import { useThemeStore } from '@/store/theme'
import { provideTheme } from '@luml/experiments'
import DetailsBreadcrumbs from '@/components/experiments/details/DetailsBreadcrumbs.vue'
import DetailsTabs from '@/components/experiments/details/DetailsTabs.vue'

const route = useRoute()
const toast = useToast()
const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()
const { provider } = useExperimentProvider()
const themeStore = useThemeStore()

provideTheme(toRef(themeStore, 'theme'))

const loading = ref(true)
const groupData = ref<Group | null>(null)

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

async function fetchData(groupId: string, experimentId: string) {
  try {
    loading.value = true
    const group = await apiService.getGroup(groupId)
    groupData.value = group
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

watch([groupId, experimentId], ([groupId, experimentId]) => fetchData(groupId, experimentId), {
  immediate: true,
})

watch(
  provider,
  (val) => {
    val ? evalsStore.setProvider(val) : evalsStore.resetProvider()
  },
  {
    immediate: true,
  },
)

onUnmounted(() => {
  experimentStore.resetExperiment()
})
</script>

<style scoped></style>
