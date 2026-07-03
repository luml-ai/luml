<template>
  <div class="forecast-chart">
    <apexchart type="line" height="360" :options="options" :series="series" />
    <div class="legend">
      <div class="legend-group">
        <span
          v-for="role in roleLegend"
          :key="role.label"
          class="legend-item"
          data-testid="role-legend-item"
        >
          <span class="swatch" :class="{ dashed: role.dashed }" :style="{ color: role.color }" />
          {{ role.label }}
        </span>
      </div>
      <div class="legend-group">
        <span
          v-for="col in columns"
          :key="col.name"
          class="legend-item series"
          :class="{ target: col.isTarget }"
          data-testid="series-legend-item"
        >
          {{ col.name }}<span v-if="col.isTarget" class="badge">target</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ApexOptions } from 'apexcharts'
import type { ForecastPoint, ForecastingChart } from '@/lib/data-processing/interfaces'
import {
  FORECAST_SEGMENT_COLORS,
  buildForecastSegments,
} from '@/lib/data-processing/forecasting-chart'

type Props = {
  chart: ForecastingChart
  targetCol: string
  knownFutureCols?: string[]
  prediction?: Record<string, ForecastPoint[]> | null
  supplied?: Record<string, ForecastPoint[]> | null
}

const props = defineProps<Props>()

const segments = computed(() =>
  buildForecastSegments(props.chart, {
    targetCol: props.targetCol,
    knownFutureCols: props.knownFutureCols,
    prediction: props.prediction,
    supplied: props.supplied,
  }),
)

const series = computed(() => segments.value.map((s) => ({ name: s.name, data: s.data })))

const options = computed<ApexOptions>(() => ({
  chart: {
    type: 'line',
    fontFamily: 'Inter, sans-serif',
    toolbar: { show: false },
    zoom: { enabled: false },
    animations: { enabled: false },
  },
  colors: segments.value.map((s) => s.color),
  stroke: {
    curve: 'straight',
    width: segments.value.map((s) => s.width),
    dashArray: segments.value.map((s) => s.dashArray),
  },
  markers: { size: segments.value.map((s) => s.markerSize), hover: { sizeOffset: 2 } },
  legend: { show: false },
  grid: { borderColor: 'var(--p-content-border-color)' },
  xaxis: {
    type: 'datetime',
    labels: { style: { colors: 'var(--p-text-muted-color)' } },
  },
  yaxis: { labels: { style: { colors: 'var(--p-text-muted-color)' } } },
  tooltip: { x: { format: 'yyyy-MM-dd' } },
}))

const roleLegend = computed(() => {
  const items = [
    { label: 'Train', color: FORECAST_SEGMENT_COLORS.train, dashed: false },
    { label: 'Test', color: FORECAST_SEGMENT_COLORS.test, dashed: false },
    { label: 'Forecast', color: FORECAST_SEGMENT_COLORS.forecast, dashed: true },
  ]
  if (props.knownFutureCols?.length) {
    items.push({ label: 'Provided', color: FORECAST_SEGMENT_COLORS.test, dashed: true })
  }
  return items
})

const columns = computed(() => {
  const names = new Set<string>()
  for (const s of segments.value) names.add(s.column)
  return [...names].map((name) => ({ name, isTarget: name === props.targetCol }))
})
</script>

<style scoped>
.forecast-chart {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}

.legend-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--p-text-muted-color);
}

.swatch {
  width: 18px;
  height: 0;
  border-top: 3px solid currentColor;
  border-radius: 2px;
}

.swatch.dashed {
  border-top-style: dashed;
}

.legend-item.series.target {
  font-weight: 600;
  color: var(--p-text-color);
}

.badge {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background-color: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}
</style>
