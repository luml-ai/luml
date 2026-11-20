<template>
  <div class="stats-card">
    <span class="title">{{ title }}</span>
    <div class="rows">
      <div v-for="row in rows" :key="row.label" class="row">
        <span>{{ row.label }}:</span>
        <span class="value" :style="{ color: row.color }">{{ row.value }}</span>
      </div>
      <span v-if="note" class="note">{{ note }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AlertStatsRow } from '@/types/alerts'

interface Props {
  title: string
  rows: AlertStatsRow[]
  note?: string
}

defineProps<Props>()
</script>

<style scoped>
.stats-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
}

.title {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.value {
  text-align: right;
  white-space: nowrap;
}

.note {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-muted-color);
}
</style>
