<template>
  <MTableCard>
    <DataTable
      :value="features"
      data-key="feature"
      scrollable
      :table-style="{ tableLayout: 'fixed', width: '100%', minWidth: `${tableMinWidth}px` }"
    >
      <Column
        field="feature"
        header="Feature"
        sortable
        :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.feature)"
      >
        <template #body="{ data: row }">
          <MEllipsis :text="row.feature" />
        </template>
      </Column>
      <Column header="Missing" :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.missing)">
        <template #body="{ data: row }">
          <MEllipsis :text="formatRate(row.missing_rate)" />
        </template>
      </Column>
      <Column header="Type errors" :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.typeErrors)">
        <template #body="{ data: row }">
          <MEllipsis :text="formatRate(row.type_error_rate)" />
        </template>
      </Column>
      <Column header="Range / unseen" :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.range)">
        <template #body="{ data: row }">
          <MEllipsis :text="getRangeLabel(row)" />
        </template>
      </Column>
      <Column
        header="Status"
        sortable
        :sort-field="getStatusSortValue"
        :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.status)"
      >
        <template #body="{ data: row }">
          <Tag
            :value="getSeverityLabel(row.status)"
            :severity="getSeverityTagSeverity(row.status)"
          />
        </template>
      </Column>
    </DataTable>
  </MTableCard>
</template>

<script setup lang="ts">
import { Column, DataTable, Tag } from 'primevue'
import type { DataQualityFeatureRow } from '@/api/monitoring/interfaces'
import { DATA_QUALITY_COLUMN_WIDTHS } from '@/constants/data-quality'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatRate, getRangeLabel, getStatusSortValue } from '@/utils/data-quality'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'
import MTableCard from '@/components/MTableCard.vue'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  features: DataQualityFeatureRow[]
}

defineProps<Props>()

const tableMinWidth = getTableMinWidth(DATA_QUALITY_COLUMN_WIDTHS)
</script>
