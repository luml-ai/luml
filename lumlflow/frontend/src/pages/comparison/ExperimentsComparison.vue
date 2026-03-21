<template>
  <div>
    <div v-if="loading">
      <Skeleton style="height: 40px; margin-bottom: 20px"></Skeleton>
      <Skeleton style="height: 31px; margin-bottom: 20px"></Skeleton>
      <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
      <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
      <div
        style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px"
      >
        <Skeleton style="height: 300px; width: 100%"></Skeleton>
        <Skeleton style="height: 300px; width: 100%"></Skeleton>
      </div>
      <Skeleton style="height: 200px; margin-bottom: 20px"></Skeleton>
    </div>
    <div
      v-else-if="error"
      class="text-center h-[calc(100vh-200px)] flex items-center justify-center"
    >
      <p class="text-muted-color">{{ error }}</p>
    </div>
    <div v-else>
      <ComparisonHeader></ComparisonHeader>
      <ComparisonModelsList
        :models-ids="experimentsIds"
        :models-list="experiments"
        :models-info="artifactsInfo"
      ></ComparisonModelsList>
      <ExperimentSnapshot
        v-if="provider"
        :provider="provider"
        :models-ids="experimentsIds"
        :models-info="artifactsInfo"
        :theme="themeStore.theme"
      ></ExperimentSnapshot>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Experiment } from '@/store/experiments/experiments.interface'
import { apiService } from '@/api/api.service'
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import { useExperimentProvider } from '@/hooks/useExperimentProvider'
import {
  ComparisonHeader,
  ComparisonModelsList,
  ExperimentSnapshot,
  useAnnotationsStore,
  type ModelsInfo,
} from '@luml/experiments'
import { getArtifactColorByIndex } from '@/helpers/colors'
import { useThemeStore } from '@/store/theme'
import { Skeleton } from 'primevue'
import { getErrorMessage } from '@/helpers/errors'

const { provider, createProvider, resetProvider } = useExperimentProvider()
const themeStore = useThemeStore()
const { allowEdit } = useAnnotationsStore()

const route = useRoute()
const toast = useToast()

const loading = ref(true)
const error = ref<string | null>(null)

const experiments = ref<Experiment[]>([])

const experimentsIds = computed(() => {
  const ids = route.query.ids
  if (!ids || typeof ids === 'string') throw new Error('Experiments IDs are required')
  return ids.map(String)
})

const artifactsInfo = computed(() => {
  return experiments.value.reduce((acc: ModelsInfo, experiment, index) => {
    const name = experiment.name
    const color = getArtifactColorByIndex(index)
    acc[experiment.id] = { name, color }
    return acc
  }, {})
})

async function fetchExperiments() {
  try {
    loading.value = true
    const promises = experimentsIds.value.map((id) => apiService.getExperiment(id))
    experiments.value = await Promise.all(promises)
  } catch (e) {
    error.value = getErrorMessage(e, 'Failed to fetch experiments')
    toast.add(errorToast(e))
  } finally {
    loading.value = false
  }
}

onBeforeMount(async () => {
  allowEdit()
  await fetchExperiments()
})

onBeforeUnmount(() => {
  resetProvider()
})

watch(
  experiments,
  (newExperiments) => {
    if (newExperiments.length > 0) {
      createProvider(newExperiments)
    } else {
      resetProvider()
    }
  },
  {
    immediate: true,
  },
)
</script>

<style scoped></style>
