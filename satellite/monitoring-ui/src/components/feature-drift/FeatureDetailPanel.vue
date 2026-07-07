<template>
  <div class="card" data-testid="feature-detail">
    <template v-if="detail">
      <div class="head">
        <div class="titles">
          <p class="section-title small mono">{{ detail.feature }}</p>
          <p class="section-subtitle">
            {{ psiLabel }}
          </p>
        </div>
        <SeverityTag :severity="detail.status" />
      </div>

      <div class="charts">
        <div class="chart">
          <p class="chart-title">Reference vs current distribution</p>
          <DistributionChart v-if="detail.distribution" :distribution="detail.distribution" />
          <p v-else class="chart-empty">No distribution available for this feature.</p>
        </div>
        <div class="chart">
          <p class="chart-title">PSI over time</p>
          <SeriesChart v-if="detail.psi_over_time" :series="detail.psi_over_time" color="#a855f7" />
          <p v-else class="chart-empty">No PSI history for this window.</p>
        </div>
      </div>
    </template>

    <p v-else class="prompt" data-testid="feature-detail-prompt">
      Select a feature from the list to inspect its reference-vs-current distribution and PSI trend.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureDriftDetail } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import DistributionChart from './DistributionChart.vue'

const props = defineProps<{ detail: FeatureDriftDetail | null | undefined }>()

const psiLabel = computed(() =>
  props.detail?.psi != null ? `PSI ${props.detail.psi.toFixed(2)}` : 'PSI not available',
)
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--luml-space-4);
  margin-bottom: var(--luml-space-4);
}
.section-title.small {
  font-size: var(--luml-text-base);
}
.charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--luml-space-5);
}
.chart-title {
  margin: 0 0 var(--luml-space-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.chart-empty,
.prompt {
  margin: var(--luml-space-2) 0 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.prompt {
  text-align: center;
  padding: var(--luml-space-6) var(--luml-space-4);
}
</style>
