<template>
  <div class="forecast-chart">
    <!-- key forces a re-mount when the segment set changes: vue3-apexcharts
         JSON-clones options on update, which strips the axis formatters -->
    <apexchart :key="chartKey" type="line" height="360" :options="options" :series="series" />
    <div class="legend">
      <div class="legend-group">
        <span
          v-for="role in roleLegend"
          :key="role.label"
          class="legend-item"
          data-testid="role-legend-item"
        >
          <span
            class="swatch"
            :class="{ dashed: role.dashed, band: role.band }"
            :style="{ color: role.color }"
          />
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
  prediction?: Record<string, ForecastPoint[]> | null
  supplied?: Record<string, ForecastPoint[]> | null
}

const props = defineProps<Props>()

const segments = computed(() =>
  buildForecastSegments(props.chart, {
    targetCol: props.targetCol,
    prediction: props.prediction,
    supplied: props.supplied,
  }),
)

// Every series is padded to the same date grid with nulls: with unequal
// x-arrays the ApexCharts hover crosshair snaps to the wrong positions and
// the shared tooltip mislabels rows.
const dateGrid = computed(() => {
  const dates = new Set<string>()
  for (const s of segments.value) for (const point of s.data) dates.add(point.x)
  return [...dates].sort()
})

const series = computed(() =>
  segments.value.map((s) => {
    const byDate = new Map(s.data.map((point) => [point.x, point.y]))
    return {
      name: s.name,
      data: dateGrid.value.map((date) => ({ x: date, y: byDate.get(date) ?? null })),
    }
  }),
)
const chartKey = computed(() => segments.value.map((s) => `${s.name}:${s.data.length}`).join('|'))
const hasBounds = computed(() => segments.value.some((s) => s.isBound))

// Per-point discrete markers: a markers.size ARRAY with mixed values breaks
// the ApexCharts crosshair/tooltip positioning (pinned to x=0), so per-series
// sizes must not be used here.
const discreteMarkers = computed(() =>
  segments.value.flatMap((s, seriesIndex) => {
    if (!s.markerSize) return []
    const byDate = new Map(s.data.map((point) => [point.x, point.y]))
    return dateGrid.value.flatMap((date, dataPointIndex) => {
      const y = byDate.get(date)
      if (y === undefined || y === null) return []
      return [
        {
          seriesIndex,
          dataPointIndex,
          size: s.markerSize,
          fillColor: s.color,
          strokeColor: 'var(--p-card-background)',
          shape: 'circle' as const,
        },
      ]
    })
  }),
)

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
  markers: { size: 0, discrete: discreteMarkers.value, hover: { sizeOffset: 2 } },
  legend: { show: false },
  grid: { borderColor: 'var(--p-content-border-color)' },
  xaxis: {
    type: 'datetime',
    labels: { style: { colors: 'var(--p-text-muted-color)' } },
  },
  yaxis: {
    labels: {
      style: { colors: 'var(--p-text-muted-color)' },
      formatter: formatAxisValue,
    },
  },
  // Custom renderer: the default shared tooltip would list a blank row for
  // every series that is null-padded at the hovered date.
  tooltip: { shared: true, intersect: false, custom: renderTooltip },
}))

function formatAxisValue(value: number): string {
  if (!Number.isFinite(value)) return ''
  return Number(value.toFixed(2)).toLocaleString('en-US')
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

type TooltipContext = {
  series: (number | null)[][]
  dataPointIndex: number
  w: { globals: { seriesX: number[][]; seriesNames: string[]; colors: string[] } }
}

function renderTooltip({ series: values, dataPointIndex, w }: TooltipContext): string {
  const timestamp = w.globals.seriesX[0]?.[dataPointIndex]
  const date = timestamp ? new Date(timestamp).toISOString().slice(0, 10) : ''
  const rows = values
    .map((seriesValues, i) => ({
      value: seriesValues[dataPointIndex],
      name: w.globals.seriesNames[i],
      color: w.globals.colors[i],
    }))
    .filter((row) => row.value !== null && Number.isFinite(row.value))
    .map(
      (row) =>
        `<div class="fc-tip-row"><span class="fc-tip-dot" style="background:${row.color}"></span>` +
        `${escapeHtml(row.name)}: <b>${formatAxisValue(row.value as number)}</b></div>`,
    )
  if (!rows.length) return ''
  return `<div class="fc-tip"><div class="fc-tip-title">${date}</div>${rows.join('')}</div>`
}

// Legend mirrors the segments actually drawn: solid lines are real values,
// dashed lines are model output, dotted lines are the confidence bounds.
const roleLegend = computed(() => {
  const present = new Set(segments.value.filter((s) => !s.isBound).map((s) => s.role))
  const items: { label: string; color: string; dashed: boolean; band?: boolean }[] = []
  if (present.has('train')) {
    items.push({ label: 'Train (actual)', color: FORECAST_SEGMENT_COLORS.train, dashed: false })
  }
  if (present.has('test')) {
    items.push({ label: 'Test (actual)', color: FORECAST_SEGMENT_COLORS.test, dashed: false })
  }
  if (present.has('testFit')) {
    items.push({ label: 'Test fit (model)', color: FORECAST_SEGMENT_COLORS.testFit, dashed: true })
  }
  if (present.has('future') || present.has('prediction')) {
    items.push({ label: 'Forecast', color: FORECAST_SEGMENT_COLORS.forecast, dashed: true })
  }
  if (present.has('supplied')) {
    items.push({ label: 'Provided', color: FORECAST_SEGMENT_COLORS.test, dashed: true })
  }
  if (hasBounds.value) {
    items.push({
      label: 'Confidence bounds',
      color: FORECAST_SEGMENT_COLORS.testFit,
      dashed: false,
      band: true,
    })
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

.swatch.band {
  border-top-width: 1px;
  border-top-style: dotted;
}

.forecast-chart :deep(.fc-tip) {
  padding: 8px 12px;
  font-size: 13px;
}

.forecast-chart :deep(.fc-tip-title) {
  margin-bottom: 6px;
  font-weight: 600;
}

.forecast-chart :deep(.fc-tip-row) {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.6;
}

.forecast-chart :deep(.fc-tip-dot) {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
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
