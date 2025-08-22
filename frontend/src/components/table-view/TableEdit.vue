<template>
  <TableEditColumns
    :target="target"
    :columns="columns"
    :selectedColumns="selectedColumns"
    :roundedButton="true"
    :buttonIcon="PenLine"
    @edit="(data) => $emit('edit', data)"
  ></TableEditColumns>
</template>

<script setup lang="ts">
import { PenLine } from 'lucide-vue-next'
import TableEditColumns from '../table/TableEditColumns.vue'

type Props = {
  target?: string
  columns: string[]
  selectedColumns: string[]
}
type Emits = {
  (event: 'edit', list: string[]): void
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped></style>
