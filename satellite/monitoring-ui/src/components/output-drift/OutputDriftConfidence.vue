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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConfidenceBlock } from '@/api/monitoring/interfaces'
import { formatOptional, formatPercent } from '@/utils/format'
import { formatPsiValue } from '@/utils/drift'
import { formatLowConfidence } from '@/utils/output-drift'
import MCard from '@/components/MCard.vue'
import FeatureDistributionChart from '@/components/feature-drift/FeatureDistributionChart.vue'
import FeatureDriftChart from '@/components/feature-drift/FeatureDriftChart.vue'
import { OUTPUT_DRIFT_CHART_HEIGHT } from '@/constants/output-drift'

interface Props {
  confidence: ConfidenceBlock
}

const props = defineProps<Props>()

const lowConfidence = computed(() => formatLowConfidence(props.confidence))
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

.footer {
  color: var(--p-text-muted-color);
}
</style>
