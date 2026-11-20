<template>
  <div class="projection">
    <div class="header">
      <h3 class="title">Multivariate drift (PCA)</h3>
      <Tag
        :value="getSeverityLabel(multivariate.status)"
        :severity="getSeverityTagSeverity(multivariate.status)"
        :dt="STATUS_TAG_TOKENS"
      />
    </div>
    <FeatureDriftChart
      title="PC1 × PC2 projection"
      subtitle="Reference vs logged, from the training PCA basis."
      empty-text="No PCA projection available for this window."
      :is-empty="isEmpty"
    >
      <PcaProjectionChart :multivariate="multivariate" />
    </FeatureDriftChart>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { MultivariatePanel } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import FeatureDriftChart from '@/components/feature-drift/FeatureDriftChart.vue'
import PcaProjectionChart from '@/components/feature-drift/PcaProjectionChart.vue'

interface Props {
  multivariate: MultivariatePanel
}

const props = defineProps<Props>()

const isEmpty = computed(
  () =>
    !props.multivariate.reference_projection.length &&
    !props.multivariate.current_projection.length,
)
</script>

<style scoped>
.projection {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.title {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
