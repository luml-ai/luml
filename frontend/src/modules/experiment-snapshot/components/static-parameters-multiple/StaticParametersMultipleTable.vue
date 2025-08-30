<template>
  <DataTable :value="data" size="small" scrollable scrollHeight="180px">
    <Column v-for="column in columns" :field="column" :header="column" :pt="{ bodyCell: 'cell' }">
      <template #body="slotProps">
        <div class="cell-content">
          <span v-tooltip.top="getParameterText(slotProps.data[column])">
            {{ getParameterText(slotProps.data[column]) }}
          </span>
        </div>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import { DataTable, Column } from 'primevue'
import { computed } from 'vue'

type Props = {
  data: Record<string, any>[]
}

const props = defineProps<Props>()

const columns = computed(() => {
  if (!props.data[0]) return []
  return Object.keys(props.data[0]).sort((a, b) => {
    if (a === 'Parameters') return -1
    return 1
  })
})

const getParameterText = computed(() => (parameter: any) => {
  const string =
    typeof parameter === 'object' && parameter.length ? parameter.join(', ') : parameter
  return string
})
</script>

<style scoped>
:deep(.cell) {
  background-color: var(--p-card-background);
}

.cell-content {
  width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
