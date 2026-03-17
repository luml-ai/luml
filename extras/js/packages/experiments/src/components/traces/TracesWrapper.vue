<template>
  <Skeleton v-if="loading" style="height: 550px; width: 100%" />
  <UiCard v-else>
    <template #header-left>
      <div class="title">
        <ListTree :size="20" color="var(--p-primary-color)" />
        <span>Traces</span>
      </div>
    </template>
    <TracesToolbar
      v-model:search="requestParams.search"
      :columns="columns"
      :selected-columns="selectedColumns"
      :export-loading="exportLoading"
      @edit="onEdit"
      @export="exportCSV"
      @filter-change="onFilterChange"
    />
    <TracesTable
      :data="tableData"
      :selected-columns="selectedColumns.length ? selectedColumns : columns"
      :artifactId="artifactId"
      :annotations-summary="annotationsSummary"
      @get-next-page="getNextPage"
      @sort="onSort"
    />
  </UiCard>
</template>

<script setup lang="ts">
import type { SortParams, TracesWrapperProps } from './traces.interface'
import type { FilterItem } from '../table/filter/filter.interface'
import type { Trace } from '@/providers/ExperimentSnapshotApiProvider.interface'
import type { GetTracesParams } from '@/interfaces/interfaces'
import type { AnnotationSummary } from '../annotations/annotations.interface'
import { computed, onBeforeMount, onUnmounted, ref, watch } from 'vue'
import { useToast, Skeleton } from 'primevue'
import { ListTree } from 'lucide-vue-next'
import { useEvalsStore } from '@/store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useDebounceFn } from '@vueuse/core'
import { INITIAL_REQUEST_PARAMS } from './traces.const'
import { useAnnotationsStore } from '@/store/annotations'
import { useTracesTable } from '@/hooks/useTracesTable'
import TracesToolbar from './TracesToolbar.vue'
import TracesTable from './TracesTable.vue'
import UiCard from '../ui/UiCard.vue'

const evalsStore = useEvalsStore()
const toast = useToast()

const props = defineProps<TracesWrapperProps>()

const annotationsStore = useAnnotationsStore()

const selectedColumns = ref<string[]>([])
const requestParams = ref<GetTracesParams>({ ...INITIAL_REQUEST_PARAMS })
const data = ref<Trace[]>([])

const {
  data: tableData,
  exportCSV,
  exportLoading,
} = useTracesTable(
  data,
  computed(() => (selectedColumns.value?.length ? selectedColumns.value : columns.value)),
  computed(() => requestParams.value),
)

const loading = ref(false)
const annotationsSummary = ref<AnnotationSummary>({
  feedback: [],
  expectations: [],
})

const feedbackColumns = computed(() => {
  return annotationsSummary.value.feedback.map((item) => item.name)
})

const expectationColumns = computed(() => {
  return annotationsSummary.value.expectations.map((item) => item.name)
})

const columns = computed(() => {
  return [
    'trace_id',
    'execution_time',
    'state',
    'span_count',
    ...feedbackColumns.value,
    ...expectationColumns.value,
    'evals',
    'created_at',
  ]
})

async function getNextPage(reset: boolean = false) {
  try {
    const params = JSON.parse(JSON.stringify(requestParams.value))
    if (reset) {
      evalsStore.getProvider.resetTracesRequestParams()
    }
    const traces = await evalsStore.getProvider.getTraces(params)
    if (reset) {
      data.value = []
    }
    data.value = [...data.value, ...traces]
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  }
}

function onSort(sortParams: SortParams) {
  requestParams.value.sort_by = sortParams.sortField
  requestParams.value.order = sortParams.sortOrder
}

function onEdit(data: string[]) {
  selectedColumns.value = data
}

function onFilterChange(filters: FilterItem[]) {
  console.log('onFilterChange', filters)
}

const debouncedRequestParamsChange = useDebounceFn(async () => {
  await getNextPage(true)
}, 500)

onBeforeMount(async () => {
  try {
    loading.value = true
    await getNextPage(true)
    annotationsSummary.value = await annotationsStore.getTracesAnnotationSummary(props.artifactId)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    loading.value = false
  }
})

onUnmounted(async () => {
  await evalsStore.getProvider.resetTracesRequestParams()
})

watch(requestParams, debouncedRequestParamsChange, { deep: true })
</script>

<style scoped>
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 20px;
}
</style>
