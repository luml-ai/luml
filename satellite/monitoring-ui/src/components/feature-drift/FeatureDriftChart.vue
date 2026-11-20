<template>
  <MScalableCard :variant="variant" :title="title" :subtitle="subtitle">
    <template #default="{ scaled }">
      <div class="chart" :class="{ scaled, fixed: height }">
        <div v-if="isEmpty" class="chart-empty">{{ emptyText }}</div>
        <slot v-else />
      </div>
    </template>
  </MScalableCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DRIFT_CHART_ASPECT_RATIO } from '@/constants/drift'
import MScalableCard from '@/components/MScalableCard.vue'

interface Props {
  title: string
  subtitle?: string
  emptyText: string
  isEmpty?: boolean
  variant?: 'bordered' | 'block'
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'block',
})

const chartHeight = computed(() => (props.height ? `${props.height}px` : 'auto'))
</script>

<style scoped>
.chart {
  aspect-ratio: v-bind(DRIFT_CHART_ASPECT_RATIO);
}

.chart.fixed {
  height: v-bind(chartHeight);
  aspect-ratio: auto;
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
