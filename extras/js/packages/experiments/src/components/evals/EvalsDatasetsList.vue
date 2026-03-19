<template>
  <div>
    <Skeleton v-if="initialLoading" style="height: 210px; margin-bottom: 20px"></Skeleton>
    <div v-else-if="evalsStore.datasets?.length" class="evals-list">
      <EvalsDataset
        v-for="item of evalsStore.datasets"
        :key="item.params.dataset_id"
        :dataset-id="item.params.dataset_id"
        :data="item.data"
        :models-info="modelsInfo"
        :columns="item.columns"
        @get-next-page="getNextPage(item.params.dataset_id)"
        @filter-change="(filter) => onFilterChange(item.params.dataset_id, filter)"
        @sort="(sortParams) => onSort(item.params.dataset_id, sortParams)"
      ></EvalsDataset>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DatasetListProps, FilterInterface, SortParams } from './evals.interface'
import { onMounted, onUnmounted, ref } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useToast, Skeleton } from 'primevue'
import EvalsDataset from './EvalsDataset.vue'

defineProps<DatasetListProps>()

const evalsStore = useEvalsStore()
const toast = useToast()

const initialLoading = ref(true)

async function getNextPage(datasetId: string, reset: boolean = false) {
  try {
    if (evalsStore.loading) return
    evalsStore.setLoading(true)
    await evalsStore.getNextDatasetPage(datasetId, reset)
  } catch (error: unknown) {
    const messageText = error instanceof Error ? error.message : 'Failed to load evals dataset'
    toast.add(simpleErrorToast(messageText))
  } finally {
    evalsStore.setLoading(false)
  }
}

async function init() {
  try {
    initialLoading.value = true
    evalsStore.setLoading(true)
    await evalsStore.initDatasets()
  } catch (error: unknown) {
    const messageText = error instanceof Error ? error.message : 'Failed to load evals datasets'
    toast.add(simpleErrorToast(messageText))
  } finally {
    evalsStore.setLoading(false)
    initialLoading.value = false
  }
}

function onFilterChange(datasetId: string, filter: FilterInterface) {
  const dataset = evalsStore.datasets?.find((item) => item.params.dataset_id === datasetId)
  if (!dataset) return
  dataset.params.search = filter.search
  getNextPage(datasetId, true)
}

function onSort(datasetId: string, sortParams: SortParams) {
  const dataset = evalsStore.datasets?.find((item) => item.params.dataset_id === datasetId)
  if (!dataset) return
  dataset.params.sort_by = sortParams.sortField
  dataset.params.order = sortParams.sortOrder
  getNextPage(datasetId, true)
}

onMounted(init)

onUnmounted(() => {
  evalsStore.reset()
  evalsStore.getProvider.resetEvalsDatasetsRequestParams()
})
</script>

<style scoped>
.evals-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
