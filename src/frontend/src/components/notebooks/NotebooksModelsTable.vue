<template>
  <DataTable :value="files">
    <template #empty> No models added yet. </template>
    <Column field="name" header="Model name"></Column>
    <Column field="size" header="Size">
      <template #body="slotProps">
        <div>
          {{
            slotProps.data.size < 1000
              ? slotProps.data.size + ' B'
              : slotProps.data.size < 10000000
                ? slotProps.data.size / 1000 + ' KB'
                : slotProps.data.size / 10000000 + ' MB'
          }}
        </div>
      </template>
    </Column>
    <Column field="created" header="Created">
      <template #body="slotProps">
        <div>
          {{ new Date(slotProps.data.created).toLocaleString() }}
        </div>
      </template>
    </Column>
    <Column style="width: 70px">
      <template #body="$slot">
        <NotebooksModelAction :file="$slot.data"></NotebooksModelAction>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import { DataTable, Column } from 'primevue'
import NotebooksModelAction from './NotebooksModelAction.vue'

type Props = {
  files: unknown[]
}

defineProps<Props>()
</script>

<style>
.notebooks-table tr.p-datatable-row-expansion td {
  padding: 16px 16px 16px 57px;
}

.notebooks-table .p-datatable-row-expansion tr {
  background-color: var(--p-datatable-header-cell-background);
}

.notebooks-table .p-datatable-row-expansion tr td {
  padding: 12px 16px;
  background-color: var(--p-datatable-header-cell-background);
}

.notebooks-table tr.p-datatable-row-expansion .p-datatable-empty-message td {
  padding: 20px 16px;
  border: none;
}
</style>
