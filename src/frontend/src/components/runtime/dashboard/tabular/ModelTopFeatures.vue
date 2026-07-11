<template>
  <ol class="features-list">
    <li v-for="feature in features" :key="feature.feature_name" class="feature-item">
      <h3 class="feature-label">{{ feature.feature_name }}</h3>
      <span class="feature-value">{{ feature.scaled_importance }}%</span>
    </li>
  </ol>
</template>

<script setup lang="ts">
import type { TrainingImportance } from '@/lib/data-processing/interfaces'

type Props = {
  features: TrainingImportance[]
}

defineProps<Props>()
</script>

<style scoped>
.features-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  counter-reset: list-counter;
}
.feature-item {
  font-weight: 400;
  font-size: 14px;
  display: flex;
  align-items: center;
  list-style-type: decimal-leading-zero;
  counter-increment: list-counter;
  gap: 8px;
}
.feature-item::before {
  content: counter(list-counter) '.';
  color: var(--p-text-muted-color);
}
.feature-label {
  flex: 1 1 auto;
}
.feature-value {
  font-size: 16px;
  color: var(--p-primary-color);
  padding: 4px;
  font-weight: 500;
  flex: 0 0 auto;
}
</style>
