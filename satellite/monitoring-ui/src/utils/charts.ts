import type { SeriesPoint } from '@/api/monitoring/interfaces'

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

export function countMeasuredPoints(points: SeriesPoint[]): number {
  return points.filter((point) => point.value != null).length
}
