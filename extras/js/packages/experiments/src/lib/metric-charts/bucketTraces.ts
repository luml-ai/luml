import {
  metricStepRanges,
  type ChartSeries,
  type MetricCatalogs,
} from '@/metric-buckets/MetricBucketStore'
import type { MetricBucket } from '@/metric-buckets/types'

export interface StepRange {
  first: number
  last: number
}

export interface SeriesStyle {
  name: string
  color: string
}

export interface ScatterTrace {
  type: 'scatter'
  uid: string
  name: string
  /** Null separates the polygons of a band. */
  x: (number | null)[]
  y: (number | null)[]
  mode: 'lines' | 'lines+markers'
  line: { color: string; width: number; shape: 'linear' }
  /** Per point; only points with no drawn neighbour get a size above 0. */
  marker?: { color: string; size: number[] }
  connectgaps: false
  showlegend: false
  hoverinfo?: 'skip'
  hovertemplate?: string
  /** Per point: the value text and the detail lines (with their leading `<br>`). */
  customdata?: HoverData[]
  fill?: 'toself'
  fillcolor?: string
  hoveron?: 'points'
}

export const MIN_BUCKET_BUDGET = 100
export const MAX_BUCKET_BUDGET = 4000
export const BAND_OPACITY = 0.2
// On a dark background the light theme's alpha leaves thin spike bands almost invisible.
export const DARK_BAND_OPACITY = 0.35
/** Values beyond this are left out of `sum` and `finite_count`, so they are not drawn. */
export const DRAWN_VALUE_LIMIT = 1e290
export const ISOLATED_MARKER_SIZE = 6
// The name comes from the trace, so it is not repeated in every point's hover data.
export const LINE_HOVER_TEMPLATE =
  '<b>%{fullData.name}</b>: %{customdata[0]}%{customdata[1]}<extra></extra>'

export type HoverData = readonly [value: string, details: string]

/**
 * One bucket per CSS pixel. The planner picks the finest level that fits the budget, which can
 * give as few as a quarter of it, so a chart gets between a quarter of its width and its width.
 */
export function bucketBudgetForWidth(widthPx: number): number {
  return Math.min(MAX_BUCKET_BUDGET, Math.max(MIN_BUCKET_BUDGET, Math.floor(widthPx)))
}

export function bucketAverage(bucket: MetricBucket): number | null {
  if (bucket.finite_count === 0 || bucket.sum === null) return null
  return bucket.sum / bucket.finite_count
}

export function bucketMidpoint(bucket: MetricBucket): number {
  return (bucket.first_step + bucket.last_step) / 2
}

/** Every point is one logged value, so a band would only repeat the line. */
export function isPlainSeries(series: ChartSeries): boolean {
  return series.level === 0 || series.buckets.every((bucket) => bucket.count === 1)
}

function isDrawable(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && Math.abs(value) <= DRAWN_VALUE_LIMIT
}

function hasUndrawnValues(bucket: MetricBucket): boolean {
  return (
    bucket.finite_count < bucket.count ||
    (bucket.min !== null && !isDrawable(bucket.min)) ||
    (bucket.max !== null && !isDrawable(bucket.max))
  )
}

function finiteOr(value: number | null, fallback: number | null): number | null {
  return isDrawable(value) ? value : fallback
}

/** Band edges; an undrawn or missing edge falls back to the average, so it is left out. */
function bandEdges(bucket: MetricBucket): [number | null, number | null] {
  const average = bucketAverage(bucket)
  return [finiteOr(bucket.min, average), finiteOr(bucket.max, average)]
}

export function formatMetricValue(value: number, exact: boolean): string {
  if (exact || !Number.isFinite(value)) return String(value)
  return String(Number(value.toPrecision(6)))
}

function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}

const NO_DETAILS = ''

function hoverData(bucket: MetricBucket, exact: boolean): HoverData {
  const average = bucketAverage(bucket)
  const valueText = average === null ? 'no value' : formatMetricValue(average, exact)
  // A unified hover lists every experiment at its own nearest point, so each names its step.
  const step = bucket.count === 1 ? ` · step ${bucket.first_step}` : NO_DETAILS
  const undrawn = hasUndrawnValues(bucket)
  if (bucket.count === 1 && !undrawn) return [valueText, step]
  const lines: string[] = []
  if (bucket.count > 1) {
    const [low, high] = [finiteOr(bucket.min, null), finiteOr(bucket.max, null)]
    const range: string[] = []
    if (low !== null) range.push(`min ${formatMetricValue(low, exact)}`)
    if (high !== null) range.push(`max ${formatMetricValue(high, exact)}`)
    if (range.length) lines.push(range.join(' · '))
    lines.push(
      `${formatCount(bucket.count)} points · steps ${bucket.first_step}–${bucket.last_step}`,
    )
  }
  if (undrawn) lines.push('Contains non-finite or out-of-range values')
  return [valueText, `${step}<br>${lines.join('<br>')}`]
}

// Series objects are never mutated, so their hover data is built once however often the
// chart is drawn again (zoom, theme, another experiment's answer).
const hoverDataCache = new WeakMap<ChartSeries, HoverData[]>()

function hoverDataOf(series: ChartSeries): HoverData[] {
  let data = hoverDataCache.get(series)
  if (!data) {
    const exact = series.level === 0
    data = series.buckets.map((bucket) => hoverData(bucket, exact))
    hoverDataCache.set(series, data)
  }
  return data
}

/** The hover label Plotly shows for a point of a line trace. */
export function hoverLabel(trace: ScatterTrace, index: number): string | null {
  const data = trace.customdata?.[index]
  return data ? `<b>${trace.name}</b>: ${data[0]}${data[1]}` : null
}

/** A drawn value whose neighbours are not drawn (gaps or buckets with no finite value). */
function isolatedPoints(y: (number | null)[]): boolean[] {
  return y.map(
    (value, index) =>
      value !== null && (y[index - 1] ?? null) === null && (y[index + 1] ?? null) === null,
  )
}

function lineTrace(series: ChartSeries, style: SeriesStyle): ScatterTrace {
  const y = series.buckets.map(bucketAverage)
  const isolated = isolatedPoints(y)
  const trace: ScatterTrace = {
    type: 'scatter',
    uid: `${series.modelId}-line`,
    name: style.name,
    x: series.buckets.map(bucketMidpoint),
    y,
    mode: 'lines',
    line: { color: style.color, width: 2, shape: 'linear' },
    connectgaps: false,
    showlegend: false,
    customdata: hoverDataOf(series),
    hovertemplate: LINE_HOVER_TEMPLATE,
  }
  if (!isolated.includes(true)) return trace
  // A line needs two drawn points, so an isolated value would be invisible without a marker.
  return {
    ...trace,
    mode: 'lines+markers',
    marker: {
      color: style.color,
      size: isolated.map((alone) => (alone ? ISOLATED_MARKER_SIZE : 0)),
    },
  }
}

/** `#rgb`, `#rrggbb`, `rgb()` or `rgba()` at the given alpha; other formats are returned as is. */
export function withAlpha(color: string, alpha: number): string {
  const text = color.trim()
  const hex = /^#([\da-f]{3}|[\da-f]{6})$/i.exec(text)?.[1]
  if (hex) {
    const full = hex.length === 3 ? [...hex].map((digit) => digit + digit).join('') : hex
    const [red, green, blue] = [0, 2, 4].map((at) => parseInt(full.slice(at, at + 2), 16))
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`
  }
  const rgb = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(text)
  return rgb ? `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${alpha})` : color
}

interface BandStep {
  bucket: number
  first: number
  last: number
  low: number
  high: number
}

/**
 * The min-max band as a stepped envelope: each bucket spans its own steps, so a spike in one
 * bucket is never drawn wider than that bucket. One closed polygon per run of consecutive
 * buckets with a non-empty band; Plotly's `toself` closes each segment between nulls on its
 * own, so no fill crosses a gap.
 */
function bandTrace(series: ChartSeries, style: SeriesStyle, alpha: number): ScatterTrace {
  const x: (number | null)[] = []
  const y: (number | null)[] = []
  let run: BandStep[] = []
  const closeRun = () => {
    if (!run.length) return
    if (x.length) {
      x.push(null)
      y.push(null)
    }
    for (const step of run) {
      x.push(step.first, step.last)
      y.push(step.high, step.high)
    }
    for (const step of [...run].reverse()) {
      x.push(step.last, step.first)
      y.push(step.low, step.low)
    }
    run = []
  }
  for (const bucket of series.buckets) {
    const [low, high] = bandEdges(bucket)
    const previous = run[run.length - 1]
    if (previous && previous.bucket !== bucket.bucket - 1) closeRun()
    if (low === null || high === null || high <= low) {
      closeRun()
      continue
    }
    run.push({ bucket: bucket.bucket, first: bucket.first_step, last: bucket.last_step, low, high })
  }
  closeRun()
  return {
    type: 'scatter',
    uid: `${series.modelId}-band`,
    name: style.name,
    x,
    y,
    mode: 'lines',
    line: { color: style.color, width: 0, shape: 'linear' },
    connectgaps: false,
    showlegend: false,
    hoverinfo: 'skip',
    hoveron: 'points',
    fill: 'toself',
    // Plotly drops trace opacity on filled traces and fills opaque, so the alpha is in the colour.
    fillcolor: withAlpha(style.color, alpha),
  }
}

/** Bands first, so every experiment's line is drawn above every band. */
export function buildBucketTraces(
  series: ChartSeries[],
  styleOf: (modelId: string) => SeriesStyle,
  bandAlpha = BAND_OPACITY,
): ScatterTrace[] {
  const drawn = series.filter((item) => item.buckets.length > 0)
  const bands = drawn
    .filter((item) => !isPlainSeries(item))
    .map((item) => bandTrace(item, styleOf(item.modelId), bandAlpha))
  const lines = drawn.map((item) => lineTrace(item, styleOf(item.modelId)))
  return [...bands, ...lines]
}

/** Lowest and highest drawn value (band included) of the buckets that overlap `range`. */
export function visibleValueRange(
  series: ChartSeries[],
  range: StepRange,
): [number, number] | null {
  let low = Infinity
  let high = -Infinity
  for (const item of series) {
    const plain = isPlainSeries(item)
    for (const bucket of item.buckets) {
      if (bucket.last_step < range.first || bucket.first_step > range.last) continue
      const average = bucketAverage(bucket)
      const [bandLow, bandHigh] = plain ? [average, average] : bandEdges(bucket)
      if (bandLow !== null) low = Math.min(low, bandLow)
      if (bandHigh !== null) high = Math.max(high, bandHigh)
    }
  }
  return low <= high ? [low, high] : null
}

export function paddedRange([low, high]: [number, number], ratio = 0.05): [number, number] {
  const span = high - low
  const pad = span > 0 ? span * ratio : Math.abs(high) * ratio || 1
  return [low - pad, high + pad]
}

/** The x range to draw; a single step gets a little room so its marker is not on the edge. */
export function axisStepRange(range: StepRange): [number, number] {
  if (range.first === range.last) return [range.first - 1, range.last + 1]
  return [range.first, range.last]
}

/** Whole steps covered by a Plotly x range, kept inside the metric's own range when they meet. */
export function requestStepRange(axis: [number, number], full: StepRange): StepRange {
  const first = Math.floor(Math.min(axis[0], axis[1]))
  const last = Math.ceil(Math.max(axis[0], axis[1]))
  const clamped = { first: Math.max(first, full.first), last: Math.min(last, full.last) }
  return clamped.first <= clamped.last ? clamped : { first, last }
}

export function maxShownLevel(series: ChartSeries[]): number | null {
  const aggregated = series.filter((item) => item.buckets.length > 0 && !isPlainSeries(item))
  if (!aggregated.length) return null
  return Math.max(...aggregated.map((item) => item.level))
}

/** Every metric with its union step range over the experiments, sorted naturally by key. */
export function catalogMetricEntries(
  catalogs: MetricCatalogs,
): { key: string; range: StepRange }[] {
  const collator = new Intl.Collator('en', { numeric: true })
  return [...metricStepRanges(catalogs)]
    .map(([key, range]) => ({ key, range }))
    .sort((a, b) => collator.compare(a.key, b.key))
}
