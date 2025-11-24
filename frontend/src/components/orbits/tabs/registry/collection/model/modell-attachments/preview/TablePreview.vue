<template>
  <div class="content-table">
    <div class="table-wrapper">
      <TableView
        v-if="viewValues?.length"
        :columnsCount="getAllColumnNames.length"
        :rowsCount="viewValues.length"
        :allColumns="getAllColumnNames"
        :value="viewValues"
        :selectedColumns="getAllColumnNames"
        :exportCallback="handleExport"
        :columnTypes="columnTypes"
        :showColumnHeaderMenu="false"
        @edit="() => {}"
        @setTarget="() => {}"
        @changeGroup="() => {}"
        @changeFilters="() => {}"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import TableView from '@/components/table-view/index.vue'
import { useDataTable } from '@/hooks/useDataTable'

const props = defineProps<{
  contentBlob: Blob
  fileName: string
}>()

const {
  viewValues,
  getAllColumnNames,
  columnTypes,

  onSelectFile,
  downloadCSV,
} = useDataTable(() => ({ size: false, rows: false, columns: false }))

const loadTable = async () => {
  if (!props.contentBlob) return
  const file = new File([props.contentBlob], props.fileName)
  await onSelectFile(file)
}

const handleExport = () => {
  downloadCSV()
}

watch(() => props.contentBlob, loadTable, { immediate: true })
</script>

<style scoped>
.content-table {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.table-wrapper :deep(.wrapper) {
  margin: 0 !important;
  height: 100%;
  border: none;
  border-radius: 0;
}

.table-wrapper :deep(.p-datatable-wrapper) {
  overflow-x: auto !important;
}
</style>
