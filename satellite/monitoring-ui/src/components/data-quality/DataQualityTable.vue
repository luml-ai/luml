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
          <button
            type="button"
            class="feature-button"
            :aria-label="`Inspect ${row.feature}`"
            @click="emit('inspect', row)"
          >
            <MEllipsis :text="row.feature" />
          </button>
        </template>
      </Column>
      <Column
        field="missing_rate"
        header="Missing"
        sortable
        :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.missing)"
      >
        <template #body="{ data: row }">
          <MEllipsis
            :text="formatRate(row.missing_rate)"
            :style="{ color: getCheckColor(row.missing_rate, QualityCheck.MISSING) }"
          />
          <span v-if="formatRateDelta(row.missing_delta)" class="delta">
            {{ formatRateDelta(row.missing_delta) }}
          </span>
        </template>
      </Column>
      <Column
        field="type_error_rate"
        header="Type errors"
        sortable
        :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.typeErrors)"
      >
        <template #body="{ data: row }">
          <MEllipsis
            :text="formatRate(row.type_error_rate)"
            :style="{ color: getCheckColor(row.type_error_rate, QualityCheck.TYPE_MISMATCH) }"
          />
          <span v-if="formatRateDelta(row.type_error_delta)" class="delta">
            {{ formatRateDelta(row.type_error_delta) }}
          </span>
        </template>
      </Column>
      <Column
        field="range_unseen_rate"
        header="Range / unseen"
        sortable
        :style="getColumnStyle(DATA_QUALITY_COLUMN_WIDTHS.range)"
      >
        <template #body="{ data: row }">
          <MEllipsis
            :text="getRangeLabel(row)"
            :style="{ color: getCheckColor(row.range_unseen_rate, getRangeCheck(row)) }"
          />
          <span v-if="formatRateDelta(row.range_unseen_delta)" class="delta">
            {{ formatRateDelta(row.range_unseen_delta) }}
          </span>
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
import { DATA_QUALITY_COLUMN_WIDTHS, QualityCheck } from '@/constants/data-quality'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import {
  formatRate,
  formatRateDelta,
  getCheckColor,
  getRangeCheck,
  getRangeLabel,
  getStatusSortValue,
} from '@/utils/data-quality'
import { getColumnStyle, getTableMinWidth } from '@/utils/table'
import MTableCard from '@/components/MTableCard.vue'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  features: DataQualityFeatureRow[]
}

defineProps<Props>()

const emit = defineEmits<{
  inspect: [row: DataQualityFeatureRow]
}>()

const tableMinWidth = getTableMinWidth(DATA_QUALITY_COLUMN_WIDTHS)
</script>

<style scoped>
.feature-button {
  max-width: 100%;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.feature-button:hover {
  text-decoration: underline;
}

.feature-button:focus-visible {
  outline: 1px solid var(--p-primary-color);
  outline-offset: 2px;
}

.delta {
  display: block;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
