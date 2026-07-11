<template>
  <DataTable
    v-model:expandedRows="expandedRows"
    dataKey="name"
    :value="notebooksStore.notebooks"
    tableStyle="min-width: 50rem;"
    class="notebooks-table"
  >
    <template #empty>
      <div class="placeholder">
        You don’t have any notebook instances yet. Click “Create instance” to launch one.
      </div>
    </template>
    <Column expander style="width: 56px; text-align: center" />
    <Column field="fullname" header="Instance name" style="width: 25%"></Column>
    <Column field="createdAt" header="Created">
      <template #body="slot">
        <div>{{ new Date(slot.data.createdAt).toLocaleString() }}</div>
      </template>
    </Column>
    <Column
      field="name"
      header="Link"
      style="width: 200px"
      :pt="{ headerCell: { style: 'padding-left: 36px' } }"
    >
      <template #body="slot">
        <Button as="a" variant="text" target="_blank" :href="getLink(slot.data.name)">
          <span>JupyterLab</span>
          <ExternalLink :size="14" />
        </Button>
      </template>
    </Column>
    <Column style="width: 67px">
      <template #body="slot">
        <NotebookListActions :notebook="slot.data"></NotebookListActions>
      </template>
    </Column>
    <template #expansion="slotProps">
      <NotebooksModelsTable :files="slotProps.data.files"></NotebooksModelsTable>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { DataTable, Column, Button } from 'primevue'
import { ExternalLink } from 'lucide-vue-next'
import { useNotebooksStore } from '@/stores/notebooks'
import NotebookListActions from './NotebookListActions.vue'
import NotebooksModelsTable from './NotebooksModelsTable.vue'

const notebooksStore = useNotebooksStore()

const expandedRows = ref({})

const getLink = computed(
  () => (databaseName: string) =>
    import.meta.env.BASE_URL + 'jupyter/lab/index.html?instanceId=' + databaseName,
)
</script>

<style scoped>
.notebooks-table {
  border-top: 1px solid var(--p-datatable-body-cell-border-color);
  border-left: 1px solid var(--p-datatable-body-cell-border-color);
  border-right: 1px solid var(--p-datatable-body-cell-border-color);
}

.buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

.placeholder {
  padding: 22px 16px;
}
</style>

<style>
.notebooks-table.p-datatable tr {
  background-color: var(--p-card-background);
}

.notebooks-table tr.p-datatable-row-expansion {
  background-color: var(--p-datatable-header-cell-background);
}
</style>
