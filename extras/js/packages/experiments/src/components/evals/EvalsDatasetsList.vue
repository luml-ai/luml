<template>
  <div>
    <Skeleton v-if="loading" style="height: 210px; margin-bottom: 20px"></Skeleton>
    <div v-else-if="datasets?.length" class="evals-list">
      <EvalsDataset
        v-for="item of datasets"
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
import type { GetEvalsByDatasetParams } from '@/interfaces/interfaces'
import type {
  DatasetData,
  DatasetListProps,
  FilterInterface,
  InitialDatasetParamsType,
} from './evals.interface'
import { onMounted, onUnmounted, ref, toRaw } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useToast, Skeleton } from 'primevue'
import EvalsDataset from './EvalsDataset.vue'

const INITIAL_PARAMS: InitialDatasetParamsType = {
  limit: 20,
  sort_by: 'created_at' as GetEvalsByDatasetParams['sort_by'],
  order: 'desc' as GetEvalsByDatasetParams['order'],
  search: '',
}

defineProps<DatasetListProps>()

const evalsStore = useEvalsStore()
const toast = useToast()

const loading = ref(true)
const datasets = ref<DatasetData[] | null>(null)

async function getNextPage(datasetId: string, reset: boolean = false) {
  try {
    if (loading.value) return
    const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
    if (!dataset) throw new Error('Dataset not found')
    const params = toRaw(dataset.params)
    const provider = evalsStore.getProvider
    if (reset) await provider.resetDatasetPage(datasetId)
    const newData = await provider.getNextEvalsByDatasetId(params)
    if (reset) {
      dataset.data = []
    }
    dataset.data.push(...newData)
  } catch (error: unknown) {
    const messageText = error instanceof Error ? error.message : 'Failed to load evals dataset'
    toast.add(simpleErrorToast(messageText))
  } finally {
    loading.value = false
  }
}

async function init() {
  try {
    const datasetsIds = await evalsStore.getProvider.getUniqueDatasetsIds()
    const promises = datasetsIds.map(getInitialDataset)
    datasets.value = await Promise.all(promises)
  } catch (error: unknown) {
    const messageText = error instanceof Error ? error.message : 'Failed to load evals datasets'
    toast.add(simpleErrorToast(messageText))
  } finally {
    loading.value = false
  }
}

async function getInitialDataset(datasetId: string) {
  const columns = await evalsStore.getProvider.getEvalsColumns(datasetId)
  const params = {
    ...INITIAL_PARAMS,
    dataset_id: datasetId,
  }
  const data = await evalsStore.getProvider.getNextEvalsByDatasetId(params)
  return {
    columns,
    data,
    params,
  }
}

function onFilterChange(datasetId: string, filter: FilterInterface) {
  const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
  if (!dataset) return
  dataset.params.search = filter.search
  getNextPage(datasetId, true)
}

function onSort(datasetId: string, sortParams: { sortField: string; sortOrder: 'asc' | 'desc' }) {
  const dataset = datasets.value?.find((item) => item.params.dataset_id === datasetId)
  if (!dataset) return
  dataset.params.sort_by = sortParams.sortField as GetEvalsByDatasetParams['sort_by']
  dataset.params.order = sortParams.sortOrder
  getNextPage(datasetId, true)
}

onMounted(init)

onUnmounted(() => {
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
