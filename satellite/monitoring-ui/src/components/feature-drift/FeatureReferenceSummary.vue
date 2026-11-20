<template>
  <div class="summary">
    <span class="title">Summary statistics</span>
    <dl class="stats">
      <div v-for="stat in stats" :key="stat.label" class="stat">
        <dt>{{ stat.label }}</dt>
        <dd>{{ stat.value }}</dd>
      </div>
    </dl>
  </div>
</template>

<script setup lang="ts">
import type { ReferenceStatItem } from '@/types/reference-profile'

interface Props {
  stats: ReferenceStatItem[]
}

defineProps<Props>()
</script>

<style scoped>
.summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 422px;
  max-width: 100%;
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

.stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.stat {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.stat dd {
  margin: 0;
}
</style>
