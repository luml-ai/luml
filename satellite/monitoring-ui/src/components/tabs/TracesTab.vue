<template>
  <div>
    <MErrorState v-if="error" :error="error" @retry="reload" />
    <MEmpty v-else-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
    <div v-else class="traces">
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
        <Column field="ts" header="Time" sortable :style="getTracesColumnStyle('ts')">
          <template #body="{ data: row }">
            <MEllipsis :text="formatTimestamp(row.ts)" />
          </template>
        </Column>
        <Column field="event_id" header="Request" :style="getTracesColumnStyle('request')">
          <template #body="{ data: row }">
            <div class="request">
              <MEllipsis class="request-id" :text="row.event_id" />
              <MCopyButton :text="row.event_id" :icon-size="14" />
            </div>
          </template>
        </Column>
        <Column
          field="features_summary"
          header="Features"
          :style="getTracesColumnStyle('features')"
        >
          <template #body="{ data: row }">
            <MEllipsis :text="row.features_summary ?? '—'" />
          </template>
        </Column>
        <Column field="prediction" header="Prediction" :style="getTracesColumnStyle('prediction')">
          <template #body="{ data: row }">
            <MEllipsis :text="row.prediction ?? '—'" />
          </template>
        </Column>
        <Column field="status" header="Status" sortable :style="getTracesColumnStyle('status')">
          <template #body="{ data: row }">
            <Tag :value="getOutcomeLabel(row.status)" :severity="getTraceStatusSeverity(row)" />
          </template>
        </Column>
        <Column
          field="latency_ms"
          header="Latency"
          sortable
          :style="getTracesColumnStyle('latency')"
          header-class="numeric"
          body-class="numeric"
        >
          <template #body="{ data: row }">
            <MEllipsis :text="formatMs(row.latency_ms)" />
          </template>
        </Column>
      </DataTable>
    </div>
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
import { formatMs, formatTimestamp } from '@/utils/format'
import { getOutcomeLabel } from '@/utils/runtime'
import {
  DEFAULT_TRACES_SORT_FIELD,
  DEFAULT_TRACES_SORT_ORDER,
  TRACES_PAGE_SIZE,
} from '@/constants/traces'
import {
  getTraceStatusSeverity,
  getTracesColumnStyle,
  getTracesEmptyState,
  clampTracesOffset,
  getTracesTableMinWidth,
  normalizeTraceSort,
  toSortOrder,
  toTraceSortKey,
} from '@/utils/traces'

const tableMinWidth = getTracesTableMinWidth()

const filtersStore = useFiltersStore()

const pageState = shallowRef({ first: 0, dimensions: filtersStore.dimensions })
const sort = shallowRef({ field: DEFAULT_TRACES_SORT_FIELD, order: DEFAULT_TRACES_SORT_ORDER })

const knownTotal = shallowRef<number | null>(null)

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

function onPage(event: DataTablePageEvent) {
  pageState.value = { first: event.first, dimensions: filtersStore.dimensions }
}

function onSort(event: DataTableSortEvent) {
  sort.value = normalizeTraceSort(event.sortField, event.sortOrder)
  pageState.value = { first: 0, dimensions: filtersStore.dimensions }
}
</script>

<style scoped>
.traces {
  --p-datatable-row-background: transparent;
  --p-datatable-row-striped-background: transparent;
  --p-paginator-background: transparent;
  --p-datatable-paginator-top-border-width: 0;
  --p-datatable-paginator-bottom-border-width: 0;
  padding: 12px 12px 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
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
}

.traces :deep(.numeric) {
  text-align: right;
}

.traces :deep(.numeric .p-datatable-column-header-content) {
  justify-content: flex-end;
}
</style>
