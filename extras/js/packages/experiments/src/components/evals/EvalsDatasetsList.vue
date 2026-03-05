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
        :table-height="datasetTableHeight"
        @get-next-page="getNextPage(item.params.dataset_id)"
      ></EvalsDataset>
    </div>
  </div>
</template>

<script setup lang="ts">
import type {
  EvalsColumns,
  EvalsInfo,
  GetEvalsByDatasetParams,
  ModelsInfo,
} from '@/interfaces/interfaces'
import { onMounted, onUnmounted, ref, toRaw } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useToast, Skeleton } from 'primevue'
import EvalsDataset from './EvalsDataset.vue'

const INITIAL_PARAMS: Omit<GetEvalsByDatasetParams, 'dataset_id'> = {
  limit: 20,
  sort_by: 'created_at' as GetEvalsByDatasetParams['sort_by'],
  order: 'desc' as GetEvalsByDatasetParams['order'],
  search: '',
}

interface Props {
  modelsInfo: ModelsInfo
  loaderHeight: string
  datasetTableHeight?: string
}

interface DatasetData {
  columns: EvalsColumns
  data: EvalsInfo[]
  params: GetEvalsByDatasetParams
}

defineProps<Props>()

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
