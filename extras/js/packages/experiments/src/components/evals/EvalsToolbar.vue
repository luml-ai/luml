<template>
  <div class="toolbar">
    <TableEditColumns
      :button-icon="Bolt"
      :columns="columns"
      :rounded-button="false"
      :selected-columns="selectedColumns"
      :disabled-columns="['id']"
      @edit="(data) => $emit('edit', data)"
    ></TableEditColumns>
    <Button severity="secondary" variant="outlined" @click="$emit('export')">
      <span>Export CSV</span>
      <Download :size="14"></Download>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Bolt, Download } from 'lucide-vue-next'
import TableEditColumns from '../table/TableEditColumns.vue'

type Props = {
  columns: string[]
  selectedColumns: string[]
}

type Emits = {
  (event: 'edit', list: string[]): void
  (event: 'export'): void
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.toolbar {
  padding: 12px 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
