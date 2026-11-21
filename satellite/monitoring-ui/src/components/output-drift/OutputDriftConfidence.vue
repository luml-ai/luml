<template>
  <div class="confidence">
    <div class="cards">
      <MCard label="CONFIDENCE PSI" :content="formatPsiValue(confidence.psi)">
        <template v-if="lowConfidence" #footer>
          <span class="footer">{{ lowConfidence }}</span>
        </template>
      </MCard>
      <MCard label="MEAN CONFIDENCE" :content="formatOptional(confidence.mean, formatPercent)" />
    </div>
    <div class="charts">
      <FeatureDriftChart
        variant="bordered"
        :height="OUTPUT_DRIFT_CHART_HEIGHT"
        title="Confidence distribution"
        subtitle="how sure the model is, live vs training"
        empty-text="No confidence distribution available for this window."
        :is-empty="!confidence.distribution?.bins.length"
      >
        <FeatureDistributionChart
          v-if="confidence.distribution"
          :distribution="confidence.distribution"
          height="100%"
        />
      </FeatureDriftChart>
      <FeatureDriftChart
        variant="bordered"
        :height="OUTPUT_DRIFT_CHART_HEIGHT"
        title="Mean confidence over time"
        subtitle="average confidence per materialized window"
        empty-text="No confidence history yet — a trend needs a second materialized window."
        :is-empty="!meanOverTime?.points.length"
      >
        <MSeriesChart v-if="meanOverTime" :series="meanOverTime" height="100%" />
      </FeatureDriftChart>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConfidenceBlock } from '@/api/monitoring/interfaces'
import { formatOptional, formatPercent } from '@/utils/format'
import { formatPsiValue } from '@/utils/drift'
import { formatLowConfidence } from '@/utils/output-drift'
import MCard from '@/components/MCard.vue'
import MSeriesChart from '@/components/MSeriesChart.vue'
import FeatureDistributionChart from '@/components/feature-drift/FeatureDistributionChart.vue'
import FeatureDriftChart from '@/components/feature-drift/FeatureDriftChart.vue'
import { OUTPUT_DRIFT_CHART_HEIGHT } from '@/constants/output-drift'

interface Props {
  confidence: ConfidenceBlock
}

const props = defineProps<Props>()

const lowConfidence = computed(() => formatLowConfidence(props.confidence))

const meanOverTime = computed(() => {
  const series = props.confidence.mean_over_time
  return series ? { ...series, unit: series.unit ?? 'ratio' } : null
})
</script>

<style scoped>
.confidence {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cards {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 20px;
}

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

.footer {
  color: var(--p-text-muted-color);
}
</style>
