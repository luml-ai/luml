<template>
  <div class="cell" v-tooltip.top="valueText">{{ valueText }}</div>
</template>

<script setup lang="ts">
import type { DatasetDataTableCellProps } from './interfaces'
import { computed } from 'vue'

const props = defineProps<DatasetDataTableCellProps>()

const valueText = computed(() => {
  if (typeof props.value === 'string') return props.value
  if (typeof props.value === 'number') return props.value.toString()
  if (typeof props.value === 'boolean') return props.value.toString()
  if (typeof props.value === 'object') return JSON.stringify(props.value)
  return String(props.value ?? '')
})
</script>

<style scoped>
.cell {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;

  overflow: hidden;
  text-overflow: ellipsis;

  min-width: 248px;
}
</style>
