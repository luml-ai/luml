<template>
  <div>
    <MErrorState v-if="error" :error="error" @retry="reload" />
    <MEmpty v-else-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
    <MTableCard v-else>
      <DataTable
        :value="data?.rows ?? []"
        data-key="event_id"
        :class="{ 'table-empty': !data?.rows.length }"
        lazy
        scrollable
        :paginator="hasMultiplePages"
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
        <Column field="ts" header="Time" sortable :style="getColumnStyle(TRACES_COLUMN_WIDTHS.ts)">
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
              <MCopyButton :text="row.event_id" :icon-size="14" />
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
    <TraceDialog v-model:visible="traceVisible" :event-id="traceEventId" />
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { Column, DataTable, Tag, type DataTablePageEvent, type DataTableSortEvent } from 'primevue'
import { api } from '@/api'
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
  TRACES_PAGE_SIZE,
} from '@/constants/traces'
import {
  getTraceStatusSeverity,
  getTracesEmptyState,
  clampTracesOffset,
  normalizeTraceSort,
  toSortOrder,
  toTraceSortKey,
} from '@/utils/traces'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'

const tableMinWidth = getTableMinWidth(TRACES_COLUMN_WIDTHS)

const filtersStore = useFiltersStore()

const pageState = shallowRef({ first: 0, dimensions: filtersStore.dimensions })
const sort = shallowRef({ field: DEFAULT_TRACES_SORT_FIELD, order: DEFAULT_TRACES_SORT_ORDER })

const knownTotal = shallowRef<number | null>(null)

const traceVisible = shallowRef(false)
const traceEventId = shallowRef<string | null>(null)

const first = computed(() => {
  if (pageState.value.dimensions !== filtersStore.dimensions) return 0
  return clampTracesOffset(pageState.value.first, knownTotal.value)
})
const sortField = computed(() => sort.value.field)
const sortOrder = computed(() => sort.value.order)

const { data, loading, error, reload } = useMonitoringData(
  async (dims) => {
    const traces = await api.monitoring.getTraces(dims, {
      limit: TRACES_PAGE_SIZE,
      offset: first.value,
      sort: toTraceSortKey(sort.value.field),
      order: toSortOrder(sort.value.order),
    })
    knownTotal.value = traces.total
    return traces
  },
  () => [first.value, sort.value],
)

const hasMultiplePages = computed(() => (data.value?.total ?? 0) > TRACES_PAGE_SIZE)

const emptyState = computed(() => (data.value ? getTracesEmptyState(data.value) : null))

function openTrace(eventId: string) {
  traceEventId.value = eventId
  traceVisible.value = true
}

function onPage(event: DataTablePageEvent) {
  pageState.value = { first: event.first, dimensions: filtersStore.dimensions }
}

function onSort(event: DataTableSortEvent) {
  sort.value = normalizeTraceSort(event.sortField, event.sortOrder)
  pageState.value = { first: 0, dimensions: filtersStore.dimensions }
}
</script>

<style scoped>
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
