<template>
  <DataTable
    :value="data"
    size="small"
    scrollable
    :scrollHeight="scrollHeight"
    :tableStyle="sortedColumns.length < MIN_COLUMNS_FOR_FIXED_LAYOUT ? 'table-layout: fixed;' : ''"
  >
    <Column
      v-for="column in sortedColumns"
      :field="column.id"
      :header="column.header"
      :pt="{ bodyCell: 'cell' }"
    >
      <template #body="slotProps">
        <div
          class="cell-content"
          :style="sortedColumns.length < MIN_COLUMNS_FOR_FIXED_LAYOUT ? '' : 'width: 180px;'"
        >
          <span v-tooltip.top="getParameterText(slotProps.data[column.id])">
            {{ getParameterText(slotProps.data[column.id]) }}
          </span>
        </div>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '../../interfaces/interfaces'
import { DataTable, Column } from 'primevue'
import { computed } from 'vue'

const MIN_COLUMNS_FOR_FIXED_LAYOUT = 4

type Props = {
  data: Record<string, any>[]
  scrollHeight: string
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const columns = computed(() => {
  if (!props.data[0]) return []
  const columns = Object.keys(props.data[0])
  return columns.map((column) => ({ id: column, header: getColumnHeader(column) }))
})

const sortedColumns = computed(() => {
  return [...columns.value].sort((a, b) => {
    if (a.id === 'Parameters') return -1
    return 1
  })
})

const getParameterText = computed(() => (parameter: any) => {
  const string =
    typeof parameter === 'object' && parameter.length ? parameter.join(', ') : parameter
  return string
})

function getColumnHeader(column: string) {
  if (column === 'Parameters') return 'Parameters'
  return props.modelsInfo[column]?.name || '-'
}
</script>

<style scoped>
:deep(.cell) {
  background-color: var(--p-card-background);
}

.cell-content {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
