<template>
  <div class="table-container">
    <DataTable
      v-if="datasetsStore.tableColumns.length"
      ref="dataTableRef"
      :value="datasetsStore.tableRows"
      :rows="datasetsStore.rowsPerPage"
      :total-records="totalRecords"
      :loading="datasetsStore.loading"
      paginator
      lazy
      show-gridlines
      paginatorTemplate="FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink"
      currentPageReportTemplate="Show {first}-{last} of {totalRecords}"
      scrollable
      scrollHeight="calc(100vh - 535px)"
      @page="onPageChange"
    >
      <Column v-for="col of datasetsStore.tableColumns" :key="col" :field="col" :header="col">
        <template #body="slotProps">
          <DatasetDataTableCell :value="slotProps.data[col]" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { useDatasetsStore } from '@/stores/datasets'
import { DataTable, Column, type DataTablePageEvent } from 'primevue'
import { computed, nextTick, ref, watch } from 'vue'
import DatasetDataTableCell from './DatasetDataTableCell.vue'

const datasetsStore = useDatasetsStore()

const dataTableRef = ref()

const totalRecords = computed(() => {
  return datasetsStore.selectedSplit?.num_rows || 0
})

function onPageChange(event: DataTablePageEvent) {
  datasetsStore.setCurrentPage(event.page)
}

function resetScroll() {
  const el = dataTableRef.value?.$el
  const scrollBody = el?.querySelector('.p-datatable-table-container')
  if (scrollBody) {
    scrollBody.scrollTop = 0
  }
}

watch(
  () => datasetsStore.tableRows,
  async () => {
    await nextTick()
    resetScroll()
  },
)
</script>

<style scoped>
:deep(.p-datatable-paginator-bottom) {
  border: none;
  padding-top: 12px;
}

:deep(.p-paginator) {
  background-color: transparent;
  justify-content: flex-end;
}

:deep(.p-datatable-header-cell) {
  border-top: none;
}

:deep(td:first-child),
:deep(th:first-child) {
  border-left: none;
}

:deep(td:last-child),
:deep(th:last-child) {
  border-right: none;
}
</style>
