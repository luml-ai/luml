<template>
  <div class="table-preview">
    <div v-if="error" class="error">{{ error }}</div>

    <Skeleton v-else-if="loading" height="calc(100vh - 500px)" />

    <DataTable
      v-else-if="tableData && (tableData.rows.length || (binaryTable && tableData.headers.length))"
      :value="tableData.rows"
      :paginator="true"
      :rows="10"
      :rows-per-page-options="[10, 20, 50]"
      :total-records="tableData.rows.length"
      size="small"
    >
      <Column
        v-for="(column, index) in tableData.headers"
        :key="index"
        :field="tableData.positional ? String(index) : column"
        :header="column"
      >
        <template v-if="binaryTable" #body="{ data }">{{
          displayCell(data[tableData.positional ? index : column])
        }}</template>
      </Column>
      <template #empty>No data to display</template>
    </DataTable>

    <div v-else class="empty">No data to display</div>

    <div v-if="footer" class="row-count">{{ footer }}</div>
  </div>
</template>

<script setup lang="ts">
import type { TablePreviewProps } from '../../interfaces/interfaces'
import { computed, toRef } from 'vue'
import { useTablePreview } from '../../hooks/useTable'
import { getFileExtension } from '../../utils/fileTypes'
import { DataTable, Column, Skeleton } from 'primevue'

const props = defineProps<TablePreviewProps>()
const binaryTable = computed(() => ['arrow', 'parquet'].includes(getFileExtension(props.fileName)))
const { tableData, error, loading } = useTablePreview({
  contentBlob: toRef(() => props.contentBlob),
  fileName: toRef(() => props.fileName),
  parquetFile: toRef(() => props.parquetFile),
  totalRows: toRef(() => props.totalRows),
})

const footer = computed(() => {
  const table = tableData.value
  if (!table || (!binaryTable.value && props.totalRows === undefined)) return ''
  const shown = table.rows.length.toLocaleString('en-US')
  const total = props.totalRows ?? table.rowsCount
  return total < 0
    ? `Showing first ${shown} rows`
    : `Showing first ${shown} of ${total.toLocaleString('en-US')} rows`
})

function displayCell(value: unknown): string {
  if (value == null) return ''
  if (value instanceof Date) return value.toISOString()
  if (typeof value !== 'object') return String(value)
  return JSON.stringify(value, (_, item) => (typeof item === 'bigint' ? item.toString() : item))
}
</script>

<style scoped>
.table-preview {
  overflow: auto;
  flex: 1;
}

:deep(.p-datatable-paginator-bottom) {
  border: none;
}

.row-count {
  margin-top: 0.5rem;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}
</style>
