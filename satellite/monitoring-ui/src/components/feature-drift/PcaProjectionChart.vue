<template>
  <div class="pca-chart">
    <ul class="legend">
      <li v-for="item in PCA_LEGEND_ITEMS" :key="item.key" class="legend-item" :class="item.key">
        <span class="legend-icon" />
        {{ item.label }}
      </li>
    </ul>
    <div class="plot">
      <MApexChart type="line" height="100%" :options="options" :series="series" />
    </div>
    <span v-if="pinnedPoints.length" class="footnote">
      {{ formatPinnedPoints(pinnedPoints.length) }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ApexOptions } from 'apexcharts'
import MApexChart from '@/components/MApexChart.vue'
import type { MultivariatePanel, PcaPoint } from '@/api/monitoring/interfaces'
import { getBaseChartOptions } from '@/lib/apex-charts'
import { useCssVariables } from '@/composables/useCssVariables'
import {
  PCA_AXIS_TICKS,
  PCA_LEGEND_ITEMS,
  PCA_SERIES_COLORS,
  PCA_SERIES_INDEX,
} from '@/constants/drift'
import {
  clampPcaPoint,
  formatPcaTick,
  formatPinnedPoints,
  getPcaBounds,
  isPcaPointInBounds,
  toPcaChartPoints,
} from '@/utils/drift'

interface Props {
  multivariate: MultivariatePanel
}

const props = defineProps<Props>()

const { values: cssValues, isDark } = useCssVariables({
  border: '--p-content-border-color',
  text: '--p-text-muted-color',
  ...PCA_SERIES_COLORS,
})

const referenceEllipse = computed(() => props.multivariate.reference_ellipse ?? [])
const currentEllipse = computed(() => props.multivariate.current_ellipse ?? [])

const allPoints = computed(() => [
  ...props.multivariate.reference_projection,
  ...props.multivariate.current_projection,
])

const bounds = computed(() =>
  getPcaBounds(allPoints.value, [...referenceEllipse.value, ...currentEllipse.value]),
)

const pinnedPoints = computed(() =>
  [
    ...props.multivariate.reference_projection.map((point) => ({ point, population: 'Reference' })),
    ...props.multivariate.current_projection.map((point) => ({ point, population: 'Current' })),
  ].filter(({ point }) => !isPcaPointInBounds(point, bounds.value)),
)

interface TooltipOpts {
  seriesIndex?: number
  dataPointIndex?: number
}

function getPinnedPoint(opts?: TooltipOpts) {
  if (opts?.seriesIndex !== PCA_SERIES_INDEX.pinned || opts.dataPointIndex == null) return null
  return pinnedPoints.value[opts.dataPointIndex] ?? null
}

function getTooltipValue(value: number, axis: keyof PcaPoint, opts?: TooltipOpts): number {
  return getPinnedPoint(opts)?.point[axis] ?? value
}

function formatTooltipX(value: number, opts?: TooltipOpts): string {
  const label = `PC1 ${formatPcaTick(getTooltipValue(value, 'x', opts))}`
  const pinned = getPinnedPoint(opts)
  return pinned ? `${pinned.population} (beyond range) · ${label}` : label
}

function getVisiblePoints(points: PcaPoint[]) {
  return toPcaChartPoints(points.filter((point) => isPcaPointInBounds(point, bounds.value)))
}

const series = computed(() => [
  {
    name: 'Reference',
    type: 'scatter',
    data: getVisiblePoints(props.multivariate.reference_projection),
  },
  {
    name: 'Current',
    type: 'scatter',
    data: getVisiblePoints(props.multivariate.current_projection),
  },
  {
    name: 'Beyond range',
    type: 'scatter',
    data: toPcaChartPoints(
      pinnedPoints.value.map(({ point }) => clampPcaPoint(point, bounds.value)),
    ),
  },
  {
    name: 'Reference ellipse',
    type: 'line',
    data: toPcaChartPoints(referenceEllipse.value),
  },
  {
    name: 'Current ellipse',
    type: 'line',
    data: toPcaChartPoints(currentEllipse.value),
  },
])

const options = computed<ApexOptions>(() => {
  const base = getBaseChartOptions()
  const axisLabelStyle = { colors: cssValues.value.text, fontSize: '12px' }
  const axisTitleStyle = { color: cssValues.value.text, fontSize: '12px', fontWeight: 400 }
  return {
    ...base,
    chart: { ...base.chart, animations: { enabled: false }, foreColor: cssValues.value.text },
    colors: [
      cssValues.value.referencePoint,
      cssValues.value.current,
      cssValues.value.pinned,
      cssValues.value.referenceEllipse,
      cssValues.value.current,
    ],
    stroke: { curve: 'straight', width: [0, 0, 0, 1.5, 1.5], dashArray: [0, 0, 0, 5, 0] },
    fill: { opacity: [0.8, 0.85, 1, 1, 1] },
    markers: {
      size: [4, 4, 5, 0, 0],
      strokeWidth: [0, 0, 1, 0, 0],
      strokeColors: cssValues.value.pinnedStroke,
      hover: { sizeOffset: 1 },
    },
    legend: { show: false },
    grid: {
      borderColor: cssValues.value.border,
      strokeDashArray: 4,
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: true } },
      padding: { top: 0, right: 16, bottom: 0, left: 8 },
    },
    xaxis: {
      type: 'numeric',
      min: bounds.value.x.min,
      max: bounds.value.x.max,
      tickAmount: PCA_AXIS_TICKS - 1,
      axisBorder: { show: false },
      axisTicks: { show: false },
      tooltip: { enabled: false },
      title: { text: 'PC1', style: axisTitleStyle },
      labels: { style: axisLabelStyle, formatter: (value) => formatPcaTick(Number(value)) },
    },
    yaxis: {
      min: bounds.value.y.min,
      max: bounds.value.y.max,
      tickAmount: PCA_AXIS_TICKS - 1,
      title: { text: 'PC2', style: axisTitleStyle },
      labels: { style: axisLabelStyle, formatter: formatPcaTick },
    },
    tooltip: {
      shared: false,
      intersect: true,
      enabledOnSeries: [
        PCA_SERIES_INDEX.reference,
        PCA_SERIES_INDEX.current,
        PCA_SERIES_INDEX.pinned,
      ],
      theme: isDark.value ? 'dark' : 'light',
      x: {
        formatter: (value, opts) => formatTooltipX(Number(value), opts),
      },
      y: {
        formatter: (value, opts) => `PC2 ${formatPcaTick(getTooltipValue(value, 'y', opts))}`,
      },
    },
  }
})
</script>

<style scoped>
.pca-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100%;
}

.legend {
  --reference-ellipse: v-bind('cssValues.referenceEllipse');
  --reference-point: v-bind('cssValues.referencePoint');
  --current: v-bind('cssValues.current');
  --pinned: v-bind('cssValues.pinned');

  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 24px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.legend-icon {
  position: relative;
  flex-shrink: 0;
  width: 20px;
  height: 12px;
  border: 1.5px solid var(--legend-ellipse);
  border-radius: 50%;
}

.legend-icon::after {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--legend-point);
  content: '';
  transform: translate(-50%, -50%);
}

.legend-item.reference {
  --legend-ellipse: var(--reference-ellipse);
  --legend-point: var(--reference-point);
}

.legend-item.reference .legend-icon {
  border-style: dashed;
}

.legend-item.current {
  --legend-ellipse: var(--current);
  --legend-point: var(--current);
}

.legend-item.pinned {
  --legend-ellipse: var(--pinned);

  color: var(--pinned);
}

.legend-item.pinned .legend-icon {
  width: 8px;
  height: 8px;
}

.legend-item.pinned .legend-icon::after {
  content: none;
}

.plot {
  flex: 1;
  min-height: 0;
}

.footnote {
  font-size: 12px;
  color: var(--p-text-muted-color);
  text-align: right;
}
</style>
