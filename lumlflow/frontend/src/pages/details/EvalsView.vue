<template>
  <Skeleton v-if="showSkeleton" class="h-[calc(100vh-250px)]" height="calc(100vh-250px)"></Skeleton>
  <EmptyState v-else-if="!loading && Object.keys(evalsStore.evals || {}).length === 0" :icon="Braces" message="No evals found" />
  <div v-else-if="!loading && Object.keys(evalsStore.evals || {})" class="evals-list">
    <EvalsCard
      v-for="item of evalsStore.evals"
      :key="item[0]?.id"
      :data="item"
      :models-info="modelsInfo"
      :table-height="tableHeight"
    ></EvalsCard>
  </div>
</template>

<script setup lang="ts">
import type { /*Eval,*/ EvalScores } from '@/store/experiments/experiments.interface'
// import type { GetExperimentEvalsParams } from '@/api/api.interface'
import { useEvalsStore, type ModelsInfo } from '@luml/experiments'
import { useRoute } from 'vue-router'
import { computed, onBeforeMount, ref } from 'vue'
import { apiService } from '@/api/api.service'
// import { usePagination } from '@/hooks/usePagination'
import { useToast, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import { EvalsCard } from '@luml/experiments'
import { useExperimentStore } from '@/store/experiment'
import { useWindowSize } from '@vueuse/core'
import { Braces } from 'lucide-vue-next'
import { useDeferredLoading } from '@/hooks/useDeferredLoading'
import EmptyState from '@/components/ui/EmptyState.vue'

const experimentStore = useExperimentStore()
const evalsStore = useEvalsStore()
const { height: windowHeight } = useWindowSize()

const route = useRoute()
const toast = useToast()
// const { data, getInitialPage, isLoading } = usePagination<Eval, GetExperimentEvalsParams>(
//   apiService.getExperimentEvals,
//   {
//     experiment_id: String(route.params.experimentId),
//   },
// )

const scores = ref<EvalScores | null>(null)
const loading = ref(true)
const { showSkeleton } = useDeferredLoading(loading)

const modelsInfo = computed<ModelsInfo>(() => {
  if (!experimentStore.experiment) return {}
  return {
    [experimentStore.experiment.id]: {
      name: experimentStore.experiment.name,
      color: 'var(--p-primary-color)',
    },
  }
})

// const formattedData = computed(() => {
//   return data.value.map((item) => {
//     return {
//       ...item,
//       modelId: experimentStore.experiment?.id || '',
//     }
//   })
// })
const tableHeight = computed(() => {
  return `${windowHeight.value - 450}px`
})

async function fetchScores() {
  try {
    scores.value = await apiService.getExperimentEvalScores(String(route.params.experimentId))
  } catch (error) {
    toast.add(errorToast(error))
  }
}

onBeforeMount(async () => {
  try {
    await fetchScores()
    await evalsStore.setEvals()
    // await getInitialPage()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
