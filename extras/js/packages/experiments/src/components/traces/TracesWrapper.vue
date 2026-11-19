<template>
  <Skeleton v-if="firstLoading" style="height: 550px; width: 100%" />
  <UiCard v-else-if="showTable">
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
      @get-next-page="getNextPage()"
      @sort="onSort"
    />
  </UiCard>
</template>

<script setup lang="ts">
import type { SortParams, TracesWrapperProps } from './traces.interface'
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue'
import { useToast, Skeleton } from 'primevue'
import { ListTree } from 'lucide-vue-next'
import { showReadErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useAnnotationsStore } from '@/store/annotations'
import { useTracesTable } from '@/hooks/useTracesTable'
import { useTraceStore } from '@/store/trace'
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

const props = withDefaults(defineProps<TracesWrapperProps>(), {
  showEmptyTable: true,
})

const selectedColumns = ref<string[]>([])
const firstLoading = ref(true)
const tracesExists = ref(false)

const annotationsSummary = computed(() => annotationsStore.tracesAnnotationsSummary)

const feedbackColumns = computed(() => {
  return annotationsSummary.value?.feedback.map((item) => item.name + ' (feedback)') || []
})

const expectationColumns = computed(() => {
  return annotationsSummary.value?.expectations.map((item) => item.name + ' (expectation)') || []
})

const showTable = computed(() => props.showEmptyTable || tracesExists.value)

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

// The store outlives this view: a read that ends after it closed leaves the store alone.
let closed = false
// The table asks for the next page only when its scrolled range changes, so a request made
// while another read runs, or before the reload for new parameters, is kept for later.
let nextPagePending = false
// Failed reloads counted when the kept request asked for its reload. If one more failed, the
// kept request is dropped: only a new request retries, so a failing read is not repeated alone.
let failedReloadsAtRequest: number | null = null

function keepNextPage(fromTable: boolean) {
  if (fromTable || failedReloadsAtRequest === null) {
    failedReloadsAtRequest = traceStore.getFailedReloads()
  } else if (traceStore.getFailedReloads() > failedReloadsAtRequest) {
    nextPagePending = false
    failedReloadsAtRequest = null
    return
  }
  nextPagePending = true
  traceStore.scheduleReload()
}

async function getNextPage(reset: boolean = false, fromTable: boolean = true) {
  // The loading flag belongs to the read in flight; a refused request must not clear it.
  if (traceStore.loading) {
    if (!reset) nextPagePending = true
    return
  }
  // The rows are for older parameters, or their reload failed: reload before the next page.
  if (!reset && !traceStore.isListCurrent()) {
    keepNextPage(fromTable)
    return
  }
  // This read answers any request kept before it.
  if (!reset) {
    nextPagePending = false
    failedReloadsAtRequest = null
  }
  try {
    traceStore.setLoading(true)
    await traceStore.getNextPage(reset)
  } catch (error) {
    showReadErrorToast(toast, error, getErrorMessage(error))
  } finally {
    if (!closed) traceStore.setLoading(false)
  }
}

watch(
  () => traceStore.loading,
  (loading) => {
    if (loading || closed || !nextPagePending) return
    nextPagePending = false
    getNextPage(false, false)
  },
)

onBeforeMount(async () => {
  try {
    traceStore.setArtifactId(props.artifactId)
    firstLoading.value = true
    await getNextPage(true)
    if (closed) return
    tracesExists.value = traceStore.traces.length > 0
    await annotationsStore.getTracesAnnotationSummary(props.artifactId)
  } catch (error) {
    showReadErrorToast(toast, error, getErrorMessage(error))
  } finally {
    firstLoading.value = false
    if (!closed) traceStore.setLoading(false)
  }
})

onBeforeUnmount(async () => {
  closed = true
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
