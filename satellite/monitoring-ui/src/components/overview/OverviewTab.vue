<template>
  <section class="overview" data-testid="overview-tab">
    <div class="intro">
      <p class="section-title">Overview</p>
      <p class="section-subtitle">Runtime health and headline signals for the selected window.</p>
    </div>

    <!-- every number below is produced in the background; this says whether that is working -->
    <WorkerHealthStrip :health="workerHealth" />

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No activity in this window"
      empty-detail="The worker has not produced runtime or drift results for this window yet."
    />

    <template v-else-if="overview">
      <div class="cards grid">
        <MetricCard v-for="card in cardsForKind" :key="card.key" :card="card" />
      </div>

      <AlertBannerList
        v-if="overview.alert_banners.length"
        :banners="overview.alert_banners"
        inspectable
        @show-feature="$emit('show-feature', $event)"
        @acknowledge="$emit('acknowledge', $event)"
      />

      <div class="charts-head">
        <StepControl :granularity="granularity" @update:granularity="$emit('update:granularity', $event)" />
      </div>
      <div class="charts grid">
        <ChartFrame
          v-for="chart in charts"
          :key="chart.series.key"
          class="card"
          :title="chart.title"
          :subtitle="chart.subtitle"
          eyebrow="Runtime"
        >
          <template #default="{ height }">
            <SeriesChart :series="chart.series" :color="chart.color" :height="height" />
          </template>
        </ChartFrame>
      </div>

      <TopDriftedList v-if="modelKind === 'tabular'" :features="overview.top_drifted_features" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  AlertBanner,
  Granularity,
  ModelKind,
  OverviewResponse,
  WorkerHealthResponse,
} from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
// shared with the Runtime tab, which plots the same three series
import { runtimeCharts } from '@/lib/charts'
import StateBlock from '@/components/StateBlock.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import StepControl from '@/components/StepControl.vue'
import ChartFrame from '@/components/ChartFrame.vue'
import MetricCard from './MetricCard.vue'
import AlertBannerList from './AlertBannerList.vue'
import TopDriftedList from './TopDriftedList.vue'
import WorkerHealthStrip from './WorkerHealthStrip.vue'

defineEmits<{
  'show-feature': [AlertBanner]
  acknowledge: [AlertBanner]
  'update:granularity': [Granularity]
}>()

const props = defineProps<{
  overview: OverviewResponse | null
  status: LoadStatus
  workerHealth?: WorkerHealthResponse | null
  granularity: Granularity
  modelKind?: ModelKind
}>()

const cardsForKind = computed(() => {
  const cards = props.overview?.cards ?? []
  if (props.modelKind === 'tabular') return cards
  return cards.filter((card) => card.key !== 'drifted_features' && card.key !== 'output_drift')
})

const view = computed(() => sectionView(props.status, props.overview?.state))

const charts = computed(() => runtimeCharts(props.overview?.series))
</script>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.cards {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.charts-head {
  display: flex;
  justify-content: flex-end;
  margin-bottom: -6px;
}
.charts {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}
.section-title.small {
  font-size: var(--luml-text-base);
}
</style>
