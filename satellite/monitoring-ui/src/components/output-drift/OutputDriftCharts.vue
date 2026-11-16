<template>
  <div class="charts">
    <FeatureDriftChart
      variant="bordered"
      :height="OUTPUT_DRIFT_CHART_HEIGHT"
      title="Reference vs current distribution"
      empty-text="No distribution available for this output."
      :is-empty="!data.distribution?.bins.length"
    >
      <FeatureDistributionChart
        v-if="data.distribution"
        :distribution="data.distribution"
        height="100%"
      />
    </FeatureDriftChart>
    <FeatureDriftChart
      variant="bordered"
      :height="OUTPUT_DRIFT_CHART_HEIGHT"
      title="PSI over time"
      empty-text="No PSI history yet — a trend needs a second materialized window."
      :is-empty="!data.psi_over_time?.points.length"
    >
      <MSeriesChart v-if="data.psi_over_time" :series="data.psi_over_time" height="100%" />
    </FeatureDriftChart>
  </div>
</template>

<script setup lang="ts">
import type { OutputDriftResponse } from '@/api/monitoring/interfaces'
import MSeriesChart from '@/components/MSeriesChart.vue'
import FeatureDistributionChart from '@/components/feature-drift/FeatureDistributionChart.vue'
import FeatureDriftChart from '@/components/feature-drift/FeatureDriftChart.vue'
import { OUTPUT_DRIFT_CHART_HEIGHT } from '@/constants/output-drift'

interface Props {
  data: OutputDriftResponse
}

defineProps<Props>()
</script>

<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

@media (max-width: 720px) {
  .charts {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
