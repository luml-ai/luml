<template>
  <div class="panel">
    <FeatureDriftRanking
      :features="features"
      :selected="selectedFeature"
      @select="emit('select', $event)"
    />
    <div class="details" :class="{ loading }" :aria-busy="loading">
      <template v-if="selected">
        <FeatureDriftDetailsHeader :detail="selected" @open-reference="emit('open-reference')" />
        <FeatureDriftChart
          title="Reference vs current distribution"
          empty-text="No distribution available for this feature."
          :is-empty="!selected.distribution?.bins.length"
        >
          <FeatureDistributionChart
            v-if="selected.distribution"
            :distribution="selected.distribution"
            height="100%"
          />
        </FeatureDriftChart>
        <FeatureDriftChart
          title="PSI over time"
          empty-text="No PSI history yet — a trend needs a second materialized window."
          :is-empty="!selected.psi_over_time?.points.length"
        >
          <MSeriesChart
            v-if="selected.psi_over_time"
            :series="selected.psi_over_time"
            height="100%"
          />
        </FeatureDriftChart>
      </template>
      <MEmpty
        v-else
        title="No feature selected"
        detail="Pick a feature from the ranking to see its distribution and PSI trend."
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DriftedFeature, FeatureDriftDetail } from '@/api/monitoring/interfaces'
import FeatureDriftDetailsHeader from '@/components/feature-drift/FeatureDriftDetailsHeader.vue'
import FeatureDriftRanking from '@/components/feature-drift/FeatureDriftRanking.vue'
import MEmpty from '@/components/MEmpty.vue'
import MSeriesChart from '@/components/MSeriesChart.vue'
import FeatureDriftChart from '@/components/feature-drift/FeatureDriftChart.vue'
import FeatureDistributionChart from '@/components/feature-drift/FeatureDistributionChart.vue'

interface Props {
  features: DriftedFeature[]
  selected?: FeatureDriftDetail | null
  selectedFeature?: string | null
  loading?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  select: [feature: string]
  'open-reference': []
}>()
</script>

<style scoped>
.panel {
  display: flex;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
}

.details {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
  padding: 20px;
  transition: opacity 0.2s;
}

.details.loading {
  opacity: 0.5;
  pointer-events: none;
}

@media (max-width: 720px) {
  .panel {
    flex-direction: column;
  }
}
</style>
