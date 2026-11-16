<template>
  <Card class="class-list">
    <template #content>
      <div class="header">
        <h3 class="title">{{ title }}</h3>
        <span class="subtitle">{{ subtitle }}</span>
      </div>
      <div class="rows">
        <div v-for="(row, index) in rows" :key="`${index}:${row.label}`" class="row">
          <span class="cell label">{{ row.label }}</span>
          <span class="cell detail">{{ row.detail }}</span>
          <span class="cell value" :class="`value--${row.severity}`">{{ row.value }}</span>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import type { ClassDriftRow } from '@/types/output-drift'

interface Props {
  title: string
  subtitle: string
  rows: ClassDriftRow[]
}

defineProps<Props>()
</script>

<style scoped>
.class-list {
  border: 1px solid var(--p-content-border-color);
}

.header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.title {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.subtitle {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr) 120px;
  gap: 16px;
  padding-right: 8px;
  font-size: 16px;
  color: var(--p-text-color);
}

.row:not(:last-child) {
  border-bottom: 1px solid var(--p-divider-border-color);
}

.cell {
  overflow: hidden;
  padding: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.value {
  text-align: right;
}

.value--warning {
  color: var(--p-message-warn-color);
}

.value--critical {
  color: var(--p-message-error-color);
}
</style>
