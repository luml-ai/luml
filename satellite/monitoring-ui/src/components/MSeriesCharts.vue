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
import { CHART_HEIGHT } from '@/constants/charts'
import { getSeriesCharts } from '@/utils/charts'
import MScalableCard from '@/components/MScalableCard.vue'
import MSeriesChart from '@/components/MSeriesChart.vue'

interface Props {
  series: Series[]
}

const props = withDefaults(defineProps<Props>(), {
  series: () => [],
})

const charts = computed(() => getSeriesCharts(props.series))
</script>

<style scoped>
.charts {
  --charts-gap: 16px;
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(max(260px, (100% - 2 * var(--charts-gap)) / 3), 1fr)
  );
  gap: var(--charts-gap);
}
</style>
