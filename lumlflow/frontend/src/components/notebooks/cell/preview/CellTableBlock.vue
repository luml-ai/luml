<template>
  <div class="flex flex-col gap-2">
    <DataTable :value="rows" scrollable scrollHeight="240px" size="small">
      <Column
        v-for="column in block.columns"
        :key="column"
        :field="column"
        :header="column"
      ></Column>
    </DataTable>
    <p class="text-sm text-muted-color">{{ block.rows.length }} of {{ block.total_rows }} rows</p>
  </div>
</template>

<script setup lang="ts">
import type { CellTableBlockProps } from './preview.interface'
import { Column, DataTable } from 'primevue'
import { computed } from 'vue'

const props = defineProps<CellTableBlockProps>()

const rows = computed(() =>
  props.block.rows.map((row) =>
    Object.fromEntries(props.block.columns.map((column, index) => [column, row[index]])),
  ),
)
</script>

<style scoped></style>
