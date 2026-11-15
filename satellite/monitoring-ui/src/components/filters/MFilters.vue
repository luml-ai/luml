<template>
  <div class="filters">
    <div class="filters-row">
      <MWindowFilter />
      <MRefreshFilter />
      <MSeverityFilter />
      <MCompareFilter class="compare" />
    </div>
    <div v-if="customRangeLabel || compareRangeLabel" class="filters-row tags-row">
      <Tag v-if="customRangeLabel" :value="customRangeLabel" />
      <Tag v-if="compareRangeLabel" :value="compareRangeLabel" severity="warn" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'
import { Compare } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import MWindowFilter from './MWindowFilter.vue'
import MRefreshFilter from './MRefreshFilter.vue'
import MSeverityFilter from './MSeverityFilter.vue'
import MCompareFilter from './MCompareFilter.vue'

const filtersStore = useFiltersStore()

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

const customRangeLabel = computed(() => {
  const { isCustomMode, customStart, customEnd } = filtersStore
  if (!isCustomMode) return null
  return formatRange(customStart, customEnd)
})

const compareRangeLabel = computed(() => {
  const { compare, compareStart, compareEnd } = filtersStore
  if (compare !== Compare.CUSTOM) return null
  return formatRange(compareStart, compareEnd)
})

function formatRange(start: string | null, end: string | null) {
  if (!start || !end) return null
  return `${dateTimeFormatter.format(new Date(start))} — ${dateTimeFormatter.format(new Date(end))}`
}
</script>

<style scoped>
.filters {
  padding: 20px 0;
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 26px;
}

.filters-row:not(:last-child) {
  margin-bottom: 4px;
}

.tags-row {
  gap: 8px;
}

.compare {
  margin-left: auto;
}
</style>
