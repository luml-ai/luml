<template>
  <div class="table-preview">
    <div v-if="error" class="error">{{ error }}</div>

    <Skeleton v-else-if="loading" height="calc(100vh - 500px)"></Skeleton>

    <DataTable
      v-else-if="tableData && tableData.rows.length > 0"
      :value="tableData.rows"
      :paginator="true"
      :rows="10"
      :rows-per-page-options="[10, 20, 50]"
      :total-records="tableData.rowsCount"
      size="small"
    >
      <Column
        v-for="column in tableData.headers"
        :key="column"
        :field="column"
        :header="column"
      ></Column>
    </DataTable>

    <div v-else class="empty">No data to display</div>
  </div>
</template>

<script setup lang="ts">
import type { TablePreviewProps } from '../../interfaces/interfaces'
import { toRef } from 'vue'
import { useTablePreview } from '../../hooks/useTable'
import { DataTable, Column, Skeleton } from 'primevue'

const props = defineProps<TablePreviewProps>()

const { tableData, error, loading } = useTablePreview({
  contentBlob: toRef(() => props.contentBlob),
  fileName: toRef(() => props.fileName),
})
</script>

<style scoped>
.table-preview {
  overflow: auto;
  flex: 1;
}

:deep(.p-datatable-paginator-bottom) {
  border: none;
}
</style>
