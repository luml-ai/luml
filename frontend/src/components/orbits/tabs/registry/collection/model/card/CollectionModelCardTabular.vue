<template>
  <div class="model-info">
    <ModelTabularPerformance
      :total-score="totalScore"
      :test-metrics="testMetrics"
      :training-metrics="trainMetrics"
      :tag="tag"
      grid-metrics
    ></ModelTabularPerformance>
    <div class="features card">
      <header class="card-header">
        <h3 class="card-title">Top {{ features.length + 1 }} features</h3>
      </header>
      <ol class="features-list">
        <li v-for="(feature, index) in features" :key="feature.feature_name" class="feature">
          <div class="feature__count">{{ index + 1 }}.</div>
          <div class="feature__name">
            {{ feature.feature_name }}
          </div>
          <div class="feature__value">{{ feature.scaled_importance }}%</div>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TabularMetrics } from '@/lib/data-processing/interfaces'
import { FnnxService, type FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import { computed } from 'vue'
import ModelTabularPerformance from '@/components/model/ModelTabularPerformance.vue'

type Props = {
  tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM
  metrics: TabularMetrics
}

const props = defineProps<Props>()

const features = computed(() => {
  return FnnxService.getTop5TabularFeatures(props.metrics)
})
const totalScore = computed(() => {
  return FnnxService.getTabularTotalScore(props.metrics)
})
const testMetrics = computed(() => {
  return FnnxService.prepareTabularMetrics(
    props.metrics.performance.eval_cv || props.metrics.performance.eval_holdout!,
    props.tag,
  )
})
const trainMetrics = computed(() => {
  return FnnxService.prepareTabularMetrics(props.metrics.performance.train, props.tag)
})
</script>

<style scoped>
.model-info {
  display: grid;
  grid-template-columns: 55% 1fr;
  gap: 20px;
  align-items: flex-start;
}

.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.card-title--medium {
  font-weight: 500;
}

.features-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.feature__count {
  flex: 0 0 auto;
  color: var(--p-text-muted-color);
}

.feature__name {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
}

.feature__value {
  flex: 0 0 auto;
  font-size: 16px;
  padding: 4px;
  font-weight: 500;
  color: var(--p-primary-500);
}
</style>
