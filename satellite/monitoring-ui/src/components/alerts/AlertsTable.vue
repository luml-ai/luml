<template>
  <MTableCard>
    <div class="header">
      <AlertsSummary :groups="groups" />
      <Button
        v-if="freshKeys.size"
        :label="freshLabel"
        size="small"
        severity="warn"
        variant="outlined"
        @click="emit('seen')"
      >
        <template #icon>
          <BellRing :size="14" />
        </template>
      </Button>
    </div>
    <DataTable
      :value="rows"
      :data-key="getAlertKey"
      :row-class="getRowClass"
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
            <button type="button" class="name-button" @click="emit('select', row)">
              <MEllipsis :text="getAlertName(row)" />
            </button>
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
          <span
            v-if="isAlertAcknowledged(row)"
            class="seen"
            title="Someone has acknowledged this alert; it stays until the metric recovers"
          >
            <Check :size="12" />
            Seen
          </span>
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
import { Button, Column, DataTable, Tag, type DataTableSortEvent } from 'primevue'
import { BellRing, Check } from 'lucide-vue-next'
import type { AlertBanner, AlertGroup } from '@/api/monitoring/interfaces'
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
  isAlertAcknowledged,
  isAlertSortField,
} from '@/utils/alerts'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'
import MTableCard from '@/components/MTableCard.vue'
import MEllipsis from '@/components/MEllipsis.vue'
import AlertsSummary from '@/components/alerts/AlertsSummary.vue'

interface Props {
  groups: AlertGroup[]
  freshKeys?: Set<string>
}

interface Emits {
  select: [alert: AlertBanner]
  seen: []
}

const props = withDefaults(defineProps<Props>(), {
  freshKeys: () => new Set(),
})

const emit = defineEmits<Emits>()

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

const freshLabel = computed(() => {
  const count = props.freshKeys.size
  return `${count} new ${count === 1 ? 'alert' : 'alerts'} — mark seen`
})

function getRowClass(row: AlertBanner) {
  return props.freshKeys.has(getAlertKey(row)) ? 'row--fresh' : undefined
}

function onSort(event: DataTableSortEvent) {
  const field = isAlertSortField(event.sortField) ? event.sortField : null
  sort.value = { field, order: event.sortOrder === -1 ? -1 : 1 }
}
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.seen {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

:deep(.row--fresh) {
  background: var(--p-highlight-background);
}

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

.name-button {
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

.name-button:hover {
  text-decoration: underline;
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
