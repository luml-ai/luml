<template>
  <div>
    <MErrorState v-if="error" :error="error" @retry="reload" />
    <MEmpty v-else-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
    <div v-else class="traces">
      <Button
        v-if="newCount"
        class="new-traces"
        :label="newTracesLabel"
        size="small"
        variant="outlined"
        @click="showLatest"
      >
        <template #icon>
          <ArrowUp :size="14" />
        </template>
      </Button>
      <MTableCard>
        <DataTable
          :value="data?.rows ?? []"
          data-key="event_id"
          :class="{ 'table-empty': !data?.rows.length }"
          lazy
          scrollable
          :paginator="hasRows"
          :paginator-template="TRACES_PAGINATOR_TEMPLATE"
          :current-page-report-template="TRACES_PAGE_REPORT_TEMPLATE"
          :row-class="getRowClass"
          :loading="loading"
          :rows="TRACES_PAGE_SIZE"
          :first="first"
          :total-records="data?.total ?? 0"
          :sort-field="sortField"
          :sort-order="sortOrder"
          :table-style="{
            tableLayout: 'fixed',
            width: '100%',
            minWidth: `${tableMinWidth}px`,
          }"
          @page="onPage"
          @sort="onSort"
        >
          <Column
            field="ts"
            header="Time"
            sortable
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.ts)"
          >
            <template #body="{ data: row }">
              <MEllipsis :text="formatTimestamp(row.ts)" />
            </template>
          </Column>
          <Column
            field="event_id"
            header="Request"
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.request)"
          >
            <template #body="{ data: row }">
              <div class="request">
                <button type="button" class="request-id" @click="openTrace(row.event_id)">
                  <MEllipsis :text="row.event_id" />
                </button>
                <MCopyButton :text="row.event_id" label="request ID" :icon-size="14" />
              </div>
            </template>
          </Column>
          <Column
            field="features_summary"
            header="Features"
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.features)"
          >
            <template #body="{ data: row }">
              <MEllipsis :text="row.features_summary ?? '—'" />
            </template>
          </Column>
          <Column
            field="prediction"
            header="Prediction"
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.prediction)"
          >
            <template #body="{ data: row }">
              <MEllipsis :text="row.prediction ?? '—'" />
            </template>
          </Column>
          <Column
            field="status"
            header="Status"
            sortable
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.status)"
          >
            <template #body="{ data: row }">
              <Tag :value="getOutcomeLabel(row.status)" :severity="getTraceStatusSeverity(row)" />
            </template>
          </Column>
          <Column
            field="latency_ms"
            header="Latency"
            sortable
            :style="getColumnStyle(TRACES_COLUMN_WIDTHS.latency)"
            header-class="numeric"
            body-class="numeric"
          >
            <template #body="{ data: row }">
              <MEllipsis :text="formatMs(row.latency_ms)" />
            </template>
          </Column>
        </DataTable>
      </MTableCard>
    </div>
    <TraceDialog v-model:visible="traceVisible" :event-id="traceEventId" />
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import {
  Button,
  Column,
  DataTable,
  Tag,
  type DataTablePageEvent,
  type DataTableSortEvent,
} from 'primevue'
import { useSessionStorage } from '@vueuse/core'
import { ArrowUp } from 'lucide-vue-next'
import { api } from '@/api'
import type { Dimensions, TraceRow, TracesResponse } from '@/api/monitoring/interfaces'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useFiltersStore } from '@/store/filters'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MCopyButton from '@/components/MCopyButton.vue'
import MEllipsis from '@/components/MEllipsis.vue'
import MTableCard from '@/components/MTableCard.vue'
import TraceDialog from '@/components/traces/TraceDialog.vue'
import { formatMs, formatTimestamp } from '@/utils/format'
import { getOutcomeLabel } from '@/utils/runtime'
import {
  DEFAULT_TRACES_SORT_FIELD,
  DEFAULT_TRACES_SORT_ORDER,
  TRACES_COLUMN_WIDTHS,
  TRACES_PAGE_REPORT_TEMPLATE,
  TRACES_PAGE_SIZE,
  TRACES_PAGINATOR_TEMPLATE,
  TRACES_SORT_STORAGE_KEY,
} from '@/constants/traces'
import {
  getTraceStatusSeverity,
  getTracesEmptyState,
  clampTracesOffset,
  countNewTraces,
  formatNewTracesLabel,
  getFreshTraceIds,
  getNextTraceSort,
  isLatestTracesQuery,
  isSameTracesQuery,
  normalizeTraceSort,
  toSortOrder,
  toTraceSortKey,
  type TracesQuery,
} from '@/utils/traces'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'

const tableMinWidth = getTableMinWidth(TRACES_COLUMN_WIDTHS)

const filtersStore = useFiltersStore()

const storedSort = useSessionStorage<{ field: string; order: number }>(TRACES_SORT_STORAGE_KEY, {
  field: DEFAULT_TRACES_SORT_FIELD,
  order: DEFAULT_TRACES_SORT_ORDER,
})

const pageState = shallowRef({ first: 0, dimensions: filtersStore.dimensions })

const knownTotal = shallowRef<number | null>(null)
const newCount = shallowRef(0)
const freshIds = shallowRef<ReadonlySet<string>>(new Set())

const traceVisible = shallowRef(false)
const traceEventId = shallowRef<string | null>(null)

let traceRequestId = 0
let lastQuery: TracesQuery | null = null
let lastTraces: TracesResponse | null = null
let latestPageIds: ReadonlySet<string> | null = null
let latestTopId: string | null = null
let lastLatestDimensions: Dimensions | null = null

const sort = computed(() => normalizeTraceSort(storedSort.value?.field, storedSort.value?.order))
const first = computed(() => {
  if (pageState.value.dimensions !== filtersStore.dimensions) return 0
  return clampTracesOffset(pageState.value.first, knownTotal.value)
})
const sortField = computed(() => sort.value.field)
const sortOrder = computed(() => sort.value.order)

const { data, loading, error, reload } = useMonitoringData(
  async (dims) => {
    const query: TracesQuery = { dimensions: dims, first: first.value, sort: sort.value }
    const id = ++traceRequestId
    if (
      lastTraces &&
      lastQuery &&
      isSameTracesQuery(lastQuery, query) &&
      !isLatestTracesQuery(query)
    ) {
      await peekNewTraces(dims, id)
      return lastTraces
    }
    const traces = await api.monitoring.getTraces(dims, {
      limit: TRACES_PAGE_SIZE,
      offset: query.first,
      sort: toTraceSortKey(query.sort.field),
      order: toSortOrder(query.sort.order),
    })
    if (id === traceRequestId) applyTraces(query, traces)
    return traces
  },
  () => [first.value, sort.value],
)

const hasRows = computed(() => (data.value?.total ?? 0) > 0)

const emptyState = computed(() => (data.value ? getTracesEmptyState(data.value) : null))

const newTracesLabel = computed(() => formatNewTracesLabel(newCount.value, TRACES_PAGE_SIZE))

function applyTraces(query: TracesQuery, traces: TracesResponse) {
  knownTotal.value = traces.total
  newCount.value = 0
  lastQuery = query
  lastTraces = traces
  if (!isLatestTracesQuery(query)) {
    freshIds.value = new Set()
    latestPageIds = null
    return
  }
  const previousIds = lastLatestDimensions === query.dimensions ? latestPageIds : null
  freshIds.value = previousIds ? getFreshTraceIds(traces.rows, previousIds) : new Set()
  latestPageIds = new Set(traces.rows.map((row) => row.event_id))
  latestTopId = traces.rows[0]?.event_id ?? null
  lastLatestDimensions = query.dimensions
}

async function peekNewTraces(dims: Dimensions, id: number) {
  if (latestTopId === null) return
  const latest = await api.monitoring.getTraces(dims, {
    limit: TRACES_PAGE_SIZE,
    offset: 0,
    sort: toTraceSortKey(DEFAULT_TRACES_SORT_FIELD),
    order: toSortOrder(DEFAULT_TRACES_SORT_ORDER),
  })
  if (id === traceRequestId) newCount.value = countNewTraces(latest.rows, latestTopId)
}

function getRowClass(row: TraceRow) {
  return freshIds.value.has(row.event_id) ? 'row--fresh' : undefined
}

function showLatest() {
  storedSort.value = { field: DEFAULT_TRACES_SORT_FIELD, order: DEFAULT_TRACES_SORT_ORDER }
  pageState.value = { first: 0, dimensions: filtersStore.dimensions }
}

function openTrace(eventId: string) {
  traceEventId.value = eventId
  traceVisible.value = true
}

function onPage(event: DataTablePageEvent) {
  pageState.value = { first: event.first, dimensions: filtersStore.dimensions }
}

function onSort(event: DataTableSortEvent) {
  storedSort.value = getNextTraceSort(sort.value, event.sortField, event.sortOrder)
  pageState.value = { first: 0, dimensions: filtersStore.dimensions }
}
</script>

<style scoped>
.traces {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.new-traces {
  align-self: flex-start;
}

:deep(.row--fresh) {
  animation: fresh-row 3s ease-out;
}

@keyframes fresh-row {
  from {
    background: var(--p-highlight-background);
  }
}

.table-empty :deep(.p-datatable-tbody) {
  height: 300px;
}

.request {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.request-id {
  flex: 1;
  min-width: 0;
  padding: 0;
  border: none;
  background: none;
  color: var(--p-primary-color);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.request-id:hover {
  text-decoration: underline;
}
</style>
