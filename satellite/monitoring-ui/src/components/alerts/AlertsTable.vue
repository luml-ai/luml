<template>
  <MTableCard>
    <AlertsSummary :groups="groups" />
    <DataTable
      :value="rows"
      :data-key="getAlertKey"
      lazy
      scrollable
      row-group-mode="subheader"
      group-rows-by="group"
      :sort-field="sort.field ?? undefined"
      :sort-order="sort.order"
      :table-style="{ tableLayout: 'fixed', width: '100%', minWidth: `${tableMinWidth}px` }"
      :pt="{ rowGroupHeaderCell: { colspan: columnsCount } }"
      @sort="onSort"
    >
      <template #groupheader="{ data: row }">
        <span class="group">{{ getAlertGroupLabel(row.group) }} {{ groupCounts[row.group] }}</span>
      </template>
      <Column
        :field="AlertSortField.NAME"
        header="Alert"
        sortable
        :style="getColumnStyle(ALERTS_COLUMN_WIDTHS.name)"
      >
        <template #body="{ data: row }">
          <div class="name">
            <span class="dot" :class="`dot--${row.severity}`" />
            <MEllipsis :text="getAlertName(row)" />
          </div>
        </template>
      </Column>
      <Column
        :field="AlertSortField.SEEN"
        header="Seen"
        sortable
        :style="getColumnStyle(ALERTS_COLUMN_WIDTHS.seen)"
      >
        <template #body="{ data: row }">
          <MEllipsis :text="formatTimestamp(row.last_seen)" />
        </template>
      </Column>
      <Column
        :field="AlertSortField.VALUE"
        header="Value"
        sortable
        :style="getColumnStyle(ALERTS_COLUMN_WIDTHS.value)"
      >
        <template #body="{ data: row }">
          <MEllipsis :text="getAlertValue(row)" />
        </template>
      </Column>
      <Column
        :field="AlertSortField.TYPE"
        header="Type"
        sortable
        :style="getColumnStyle(ALERTS_COLUMN_WIDTHS.type)"
      >
        <template #body="{ data: row }">
          <Tag
            :value="getSeverityLabel(row.severity)"
            :severity="getSeverityTagSeverity(row.severity)"
          />
        </template>
      </Column>
      <Column
        :field="AlertSortField.DURATION"
        header="Duration"
        sortable
        :style="getColumnStyle(ALERTS_COLUMN_WIDTHS.duration)"
        header-class="numeric"
        body-class="numeric"
      >
        <template #body="{ data: row }">
          <MEllipsis :text="formatDuration(row.duration_seconds)" />
        </template>
      </Column>
    </DataTable>
  </MTableCard>
</template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { Column, DataTable, Tag, type DataTableSortEvent } from 'primevue'
import type { AlertGroup } from '@/api/monitoring/interfaces'
import { ALERTS_COLUMN_WIDTHS, AlertSortField } from '@/constants/alerts'
import type { TableSortOrder } from '@/constants/traces'
import {
  formatDuration,
  getAlertGroupLabel,
  getAlertKey,
  getAlertName,
  getAlertValue,
  getSeverityLabel,
  getSeverityTagSeverity,
  getSortedAlerts,
  isAlertSortField,
} from '@/utils/alerts'
import { formatTimestamp } from '@/utils/format'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'
import MTableCard from '@/components/MTableCard.vue'
import MEllipsis from '@/components/MEllipsis.vue'
import AlertsSummary from '@/components/alerts/AlertsSummary.vue'

interface Props {
  groups: AlertGroup[]
}

const props = defineProps<Props>()

const tableMinWidth = getTableMinWidth(ALERTS_COLUMN_WIDTHS)

const columnsCount = Object.keys(ALERTS_COLUMN_WIDTHS).length

const sort = shallowRef<{ field: AlertSortField | null; order: TableSortOrder }>({
  field: null,
  order: 1,
})

const rows = computed(() => getSortedAlerts(props.groups, sort.value.field, sort.value.order))

const groupCounts = computed(() =>
  Object.fromEntries(props.groups.map(({ group, alerts }) => [group, alerts.length])),
)

function onSort(event: DataTableSortEvent) {
  const field = isAlertSortField(event.sortField) ? event.sortField : null
  sort.value = { field, order: event.sortOrder === -1 ? -1 : 1 }
}
</script>

<style scoped>
.group {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--p-badge-success-background);
}

.dot--warning {
  background: var(--p-badge-warn-background);
}

.dot--critical {
  background: var(--p-badge-danger-background);
}

:deep(.p-datatable-tbody > tr > td) {
  border-bottom-width: 0;
}

:deep(.p-datatable-row-group-header > td) {
  padding-top: 18px;
}

:deep(.p-datatable-tbody > .p-datatable-row-group-header:not(:first-child) > td) {
  border-top: 1px solid var(--p-datatable-body-cell-border-color);
}
</style>
