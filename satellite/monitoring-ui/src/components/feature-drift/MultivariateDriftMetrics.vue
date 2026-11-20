<template>
  <div class="metrics">
    <h3 class="title">How drift is measured</h3>
    <div class="list">
      <template v-for="(metric, index) in metrics" :key="metric.label">
        <Divider v-if="index > 0" :dt="{ horizontal: { margin: '8px 0' } }" />
        <div class="metric">
          <span class="value">{{ metric.value }}</span>
          <span class="label">{{ metric.label }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import Divider from 'primevue/divider'
import type { MultivariateMetric } from '@/types/drift'

interface Props {
  metrics: MultivariateMetric[]
}

defineProps<Props>()
</script>

<style scoped>
.metrics {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.title {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.list {
  display: flex;
  flex-direction: column;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.value,
.label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.value {
  font-size: 24px;
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
  color: var(--p-text-color);
}

.label {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
