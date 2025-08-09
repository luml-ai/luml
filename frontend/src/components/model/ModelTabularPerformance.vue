<template>
  <div class="performance card">
    <header class="card-header">
      <h3 class="card-title">Model performance</h3>
      <Info
        width="20"
        height="20"
        class="info-icon"
        v-tooltip.bottom="
          `Model total score is a custom metric that provides a general estimate of overall model performance. A score around 50% typically indicates random performance, while higher values reflect better predictive ability.`
        "
      />
    </header>
    <div class="radialbar-wrapper">
      <VueApexCharts
        type="radialBar"
        :series="[totalScore]"
        :options="options"
        :style="{ pointerEvents: 'none', marginTop: '-30px', height: '135px' }"
      />
    </div>
    <div class="metric-cards" :class="{ 'metric-cards--grid': gridMetrics }">
      <MetricCard
        v-for="card in metricCardsData"
        :key="card.title"
        :title="card.title"
        :items="card.items"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { getRadialBarOptions } from '@/lib/apex-charts/apex-charts'
import { Info } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { getMetricsCards } from '@/helpers/helpers'
import MetricCard from '../ui/MetricCard.vue'
import VueApexCharts from 'vue3-apexcharts'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'

type Props = {
  totalScore: number
  testMetrics: string[]
  trainingMetrics: string[]
  tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM
  gridMetrics?: boolean
  tooltip?: string
}

const props = defineProps<Props>()

const options = ref(getRadialBarOptions())

const metricCardsData = computed(() =>
  props.tag ? getMetricsCards(props.testMetrics, props.trainingMetrics, props.tag) : [],
)
</script>

<style scoped>
.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.performance {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.metric-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-cards--grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
}

.radialbar-wrapper {
  max-width: 325px;
  margin: 0 auto;
  margin-bottom: 2rem;
}

.radialbar-wrapper .vue-apexcharts {
  min-height: 0 !important;
}

.info-icon {
  color: var(--p-icon-muted-color);
}
</style>
