import type { Series, SeriesPoint } from '@/api/monitoring/interfaces'
import { DEFAULT_CHART_COLOR, SERIES_CHART_META, type ChartMeta } from '@/constants/charts'

const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 })
const compactFormat = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function formatChartValue(value: number | null | undefined, unit?: string | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  if (unit === 'ratio') return `${numberFormat.format(value * 100)}%`
  if (unit === 'ms') return `${Math.round(value)} ms`
  if (Math.abs(value) >= 10000) return compactFormat.format(value)
  return numberFormat.format(value)
}

export function toChartPoints(points: SeriesPoint[]): [number, number | null][] {
  return points.map((point) => [new Date(point.t).getTime(), point.value])
}

export function hasIsolatedPoints(points: SeriesPoint[]): boolean {
  return points.some(
    (point, index) =>
      point.value != null && points[index - 1]?.value == null && points[index + 1]?.value == null,
  )
}

export function getSeriesCharts(series: Series[]): (ChartMeta & { series: Series })[] {
  return series.map((entry) => ({
    series: entry,
    ...(SERIES_CHART_META[entry.key] ?? {
      title: entry.label,
      subtitle: '',
      color: DEFAULT_CHART_COLOR,
    }),
  }))
}
