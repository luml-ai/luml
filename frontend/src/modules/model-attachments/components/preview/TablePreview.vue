<template>
  <div class="table-preview">
    <div v-if="error" class="error">{{ error }}</div>

    <table v-else-if="tableData && tableData.rows.length">
      <thead v-if="tableData.headers.length">
        <tr>
          <th v-for="(header, index) in tableData.headers" :key="index">{{ header }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, rowIndex) in tableData.rows" :key="rowIndex">
          <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty">No data to display</div>
  </div>
</template>

<script setup lang="ts">
import { toRef } from 'vue'
import { useTablePreview } from '../../hooks/useTable'
import type { TablePreviewProps } from '../../interfaces/interfaces'

const props = defineProps<TablePreviewProps>()

const { tableData, error } = useTablePreview({
  contentBlob: toRef(() => props.contentBlob),
  fileName: toRef(() => props.fileName),
})
</script>

<style scoped>
.table-preview {
  overflow: auto;
  flex: 1;
}
</style>
