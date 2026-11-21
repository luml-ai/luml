<template>
  <div class="filters">
    <div class="filters-row">
      <MWindowFilter />
      <MRefreshFilter />
      <MSeverityFilter />
      <MCompareFilter class="compare" />
    </div>
    <div v-if="customRangeLabel || compareLabel" class="filters-row tags-row">
      <Tag v-if="customRangeLabel" :value="`Period: ${customRangeLabel}`" />
      <Tag v-if="compareLabel" :value="`Compared with: ${compareLabel}`" severity="warn" />
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
  const { isCustomRange, customStart, customEnd } = filtersStore
  if (!isCustomRange) return null
  return formatRange(customStart, customEnd)
})

const compareLabel = computed(() => {
  const { compare, compareStart, compareEnd } = filtersStore
  if (compare === Compare.PREVIOUS) return 'previous period'
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
  padding: 20px 0 0;
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
