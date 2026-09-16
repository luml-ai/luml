<template>
  <CellBarChart v-if="numericEntries" :entries="numericEntries" />
  <dl v-else class="kv-list">
    <template v-for="[name, value] in entries" :key="name">
      <dt class="kv-name">{{ name }}</dt>
      <dd class="kv-value">{{ value }}</dd>
    </template>
  </dl>
</template>

<script setup lang="ts">
import type { CellKeyValueBlockProps } from './preview.interface'
import { computed } from 'vue'
import CellBarChart from './CellBarChart.vue'

const props = defineProps<CellKeyValueBlockProps>()

const entries = computed(() => Object.entries(props.block.entries))

const numericEntries = computed<[string, number][] | null>(() => {
  const list = entries.value
  if (list.length < 2) return null
  const numeric = list.filter((entry): entry is [string, number] => typeof entry[1] === 'number')
  return numeric.length === list.length ? numeric : null
})
</script>

<style scoped>
@reference "@/assets/css/index.css";

.kv-list {
  @apply grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm;
}
.kv-name {
  @apply text-muted-color;
}
.kv-value {
  @apply font-medium wrap-break-word;
}
</style>
