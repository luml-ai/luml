<template>
  <section class="overview" data-testid="overview-tab">
    <div class="intro">
      <p class="section-title">Overview</p>
      <p class="section-subtitle">Runtime health and headline signals for the selected window.</p>
    </div>

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No activity in this window"
      empty-detail="The worker has not produced runtime or drift results for this window yet."
    />

    <template v-else-if="overview">
      <div class="cards grid">
        <MetricCard v-for="card in overview.cards" :key="card.key" :card="card" />
      </div>

      <AlertBannerList v-if="overview.alert_banners.length" :banners="overview.alert_banners" />

      <div class="charts grid">
        <div v-for="chart in charts" :key="chart.series.key" class="card">
          <p class="section-title small">{{ chart.title }}</p>
          <p class="section-subtitle">{{ chart.subtitle }}</p>
          <SeriesChart :series="chart.series" :color="chart.color" />
        </div>
      </div>

      <TopDriftedList :features="overview.top_drifted_features" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { OverviewResponse, Series } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import StateBlock from '@/components/StateBlock.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import MetricCard from './MetricCard.vue'
import AlertBannerList from './AlertBannerList.vue'
import TopDriftedList from './TopDriftedList.vue'

const props = defineProps<{ overview: OverviewResponse | null; status: LoadStatus }>()

const view = computed(() => sectionView(props.status, props.overview?.state))

const CHART_META: Record<string, { title: string; subtitle: string; color: string }> = {
  requests: {
    title: 'Requests over time',
    subtitle: 'prediction calls per interval',
    color: '#2673fd',
  },
  error_rate: {
    title: 'Error rate over time',
    subtitle: '4xx / 5xx share of calls',
    color: '#f97316',
  },
  latency_p95: {
    title: 'Latency p95 over time',
    subtitle: '95th percentile response time',
    color: '#a855f7',
  },
}

const charts = computed(() =>
  (props.overview?.series ?? []).map((series: Series) => ({
    series,
    ...(CHART_META[series.key] ?? { title: series.label, subtitle: '', color: '#2673fd' }),
  })),
)
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
.charts {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}
.section-title.small {
  font-size: var(--luml-text-base);
}
</style>
