<template>
  <MScalableCard variant="block" :title="title" :subtitle="subtitle" :dialog-ratio="dialogRatio">
    <template #default="{ scaled }">
      <div class="chart" :class="{ scaled }">
        <div v-if="isEmpty" class="chart-empty">{{ emptyText }}</div>
        <slot v-else />
      </div>
    </template>
  </MScalableCard>
</template>

<script setup lang="ts">
import { DRIFT_CHART_ASPECT_RATIO } from '@/constants/drift'
import MScalableCard from '@/components/MScalableCard.vue'

interface Props {
  title: string
  subtitle?: string
  dialogRatio?: number
  emptyText: string
  isEmpty?: boolean
}

defineProps<Props>()
</script>

<style scoped>
.chart {
  aspect-ratio: v-bind(DRIFT_CHART_ASPECT_RATIO);
}

.chart.scaled {
  height: 100%;
  aspect-ratio: auto;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--p-text-muted-color);
  text-align: center;
}
</style>
