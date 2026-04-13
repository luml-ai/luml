<template>
  <Skeleton v-if="firstLoading" style="height: 550px; width: 100%" />
  <UiCard v-else>
    <template #header-left>
      <div class="title">
        <ListTree :size="20" color="var(--p-primary-color)" />
        <span>Traces</span>
      </div>
    </template>
    <TracesToolbar
      :search="traceStore.requestParams.search"
      :columns="columns"
      :selected-columns="selectedColumns"
      :export-loading="exportLoading"
      @edit="onEdit"
      @export="exportCSV"
      @filters-change="onFilterChange"
      @update:search="onSearchUpdate"
    />
    <TracesTable
      :data="tableData"
      :selected-columns="selectedColumns.length ? selectedColumns : columns"
      :artifactId="artifactId"
      @get-next-page="getNextPage"
      @sort="onSort"
    />
  </UiCard>
</template>

<script setup lang="ts">
import type { SortParams, TracesWrapperProps } from './traces.interface'
import { computed, onBeforeMount, onBeforeUnmount, ref } from 'vue'
import { useToast, Skeleton } from 'primevue'
import { ListTree } from 'lucide-vue-next'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import { getErrorMessage } from '@experiments/helpers/helpers'
import { useAnnotationsStore } from '@experiments/store/annotations'
import { useTracesTable } from '@experiments/hooks/useTracesTable'
import { useTraceStore } from '@experiments/store/trace'
import TracesToolbar from './TracesToolbar.vue'
import TracesTable from './TracesTable.vue'
import UiCard from '../ui/UiCard.vue'

const toast = useToast()
const annotationsStore = useAnnotationsStore()
const traceStore = useTraceStore()
const {
  data: tableData,
  exportCSV,
  exportLoading,
} = useTracesTable(
  computed(() => traceStore.traces),
  computed(() => (selectedColumns.value?.length ? selectedColumns.value : columns.value)),
  computed(() => traceStore.requestParams),
)

const props = defineProps<TracesWrapperProps>()

const selectedColumns = ref<string[]>([])
const firstLoading = ref(true)

const annotationsSummary = computed(() => annotationsStore.tracesAnnotationsSummary)

const feedbackColumns = computed(() => {
  return annotationsSummary.value?.feedback.map((item) => item.name + ' (feedback)') || []
})

const expectationColumns = computed(() => {
  return annotationsSummary.value?.expectations.map((item) => item.name + ' (expectation)') || []
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

function onSort(sortParams: SortParams) {
  traceStore.setRequestParams({ sort_by: sortParams.sortField, order: sortParams.sortOrder })
}

function onEdit(data: string[]) {
  selectedColumns.value = data
}

function onFilterChange(filters: string[]) {
  traceStore.setRequestParams({ filters })
}

function onSearchUpdate(search: string) {
  traceStore.setRequestParams({ search })
}

async function getNextPage(reset: boolean = false) {
  try {
    if (traceStore.loading) return
    traceStore.setLoading(true)
    await traceStore.getNextPage(reset)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    traceStore.setLoading(false)
  }
}

onBeforeMount(async () => {
  try {
    traceStore.setArtifactId(props.artifactId)
    firstLoading.value = true
    await traceStore.getTypedColumns()
    await getNextPage(true)
    await annotationsStore.getTracesAnnotationSummary(props.artifactId)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    firstLoading.value = false
    traceStore.setLoading(false)
  }
})

onBeforeUnmount(async () => {
  traceStore.reset()
})
</script>

<style scoped>
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 20px;
}
</style>
