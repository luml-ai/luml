<template>
  <div class="charts">
    <MScalableCard
      v-for="chart in charts"
      :key="chart.series.key"
      :title="chart.title"
      :subtitle="chart.subtitle"
    >
      <template #default="{ scaled }">
        <MSeriesChart
          :series="chart.series"
          :color="chart.color"
          :height="scaled ? '100%' : CHART_HEIGHT"
        />
      </template>
    </MScalableCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Series } from '@/api/monitoring/interfaces'
import { CHART_HEIGHT, DEFAULT_CHART_COLOR, SERIES_CHART_META } from '@/constants/charts'
import MScalableCard from '@/components/MScalableCard.vue'
import MSeriesChart from '@/components/MSeriesChart.vue'

interface Props {
  series: Series[]
}

const props = withDefaults(defineProps<Props>(), {
  series: () => [],
})

const charts = computed(() =>
  props.series.map((series) => ({
    series,
    ...(SERIES_CHART_META[series.key] ?? {
      title: series.label,
      subtitle: '',
      color: DEFAULT_CHART_COLOR,
    }),
  })),
)
</script>

<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}
</style>
