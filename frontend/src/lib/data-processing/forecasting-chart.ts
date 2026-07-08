import type { ForecastPoint, ForecastingChart } from './interfaces'

/**
 * The three role colours the chart shares across every series (target and
 * auxiliaries alike). They resolve to existing Figma-generated theme tokens, so
 * they track the active light/dark theme without any hand-authored CSS.
 */
export const FORECAST_SEGMENT_COLORS = {
  train: 'var(--p-primary-color)',
  test: 'var(--p-orange-500)',
  testFit: 'var(--p-purple-500)',
  forecast: 'var(--p-teal-500)',
} as const

export type ForecastSegmentRole =
  | 'train'
  | 'test'
  | 'testFit'
  | 'future'
  | 'prediction'
  | 'supplied'

const DASH_SOLID = 0
const DASH_DASHED = 6
const DASH_DOTTED = 2
const TARGET_WIDTH = 3
const SERIES_WIDTH = 2
const FIT_MARKER_SIZE = 3
const BOUND_WIDTH = 1

const ROLE_LABEL: Record<ForecastSegmentRole, string> = {
  train: 'Train',
  test: 'Test',
  testFit: 'Test fit',
  future: 'Forecast',
  prediction: 'Forecast',
  supplied: 'Provided',
}

export interface ForecastChartSegment {
  name: string
  column: string
  role: ForecastSegmentRole
  color: string
  dashArray: number
  width: number
  markerSize: number
  isBound: boolean
  data: { x: string; y: number }[]
}

export interface ForecastChartOverlays {
  targetCol: string
  /** Normalized re-forecast result, per column (target carries bounds). */
  prediction?: Record<string, ForecastPoint[]> | null
  /** Caller-supplied known-future values, drawn as a distinct segment. */
  supplied?: Record<string, ForecastPoint[]> | null
}

function segment(
  column: string,
  role: ForecastSegmentRole,
  color: string,
  dashArray: number,
  width: number,
  markerSize: number,
  points: ForecastPoint[],
): ForecastChartSegment {
  return {
    name: `${column} (${ROLE_LABEL[role]})`,
    column,
    role,
    color,
    dashArray,
    width,
    markerSize,
    isBound: false,
    data: points.map((point) => ({ x: point.date, y: point.value })),
  }
}

/**
 * Thin dotted confidence-bound lines for points that carry lower/upper bounds
 * (the target series). Drawn as plain line series: rangeArea combos break the
 * ApexCharts hover tooltip, and a shaded band cannot be used here.
 */
function boundSegments(
  column: string,
  role: ForecastSegmentRole,
  color: string,
  points: ForecastPoint[],
): ForecastChartSegment[] {
  const bounded = points.filter(
    (point) => point.lower !== undefined && point.upper !== undefined,
  )
  if (bounded.length < 2) return []
  const bound = (label: 'low' | 'high', pick: (p: ForecastPoint) => number | undefined) => ({
    name: `${column} (${ROLE_LABEL[role]} ${label})`,
    column,
    role,
    color,
    dashArray: DASH_DOTTED,
    width: BOUND_WIDTH,
    markerSize: 0,
    isBound: true,
    data: bounded.map((point) => ({ x: point.date, y: pick(point) as number })),
  })
  return [bound('low', (p) => p.lower), bound('high', (p) => p.upper)]
}

/**
 * Split the actual observations at the chronological train/test boundary. ISO
 * `YYYY-MM-DD` strings sort lexicographically, so plain comparison is a valid
 * date comparison. The last train point is repeated at the head of the test
 * segment so the two coloured lines join with no visual gap.
 */
function splitActuals(
  actuals: ForecastPoint[],
  splitDate: string | null,
): { train: ForecastPoint[]; test: ForecastPoint[] } {
  if (!splitDate) return { train: actuals, test: [] }
  const train = actuals.filter((point) => point.date < splitDate)
  const test = actuals.filter((point) => point.date >= splitDate)
  if (train.length && test.length) return { train, test: [train[train.length - 1], ...test] }
  return { train, test }
}

/** Target first, then auxiliaries in chart order, restricted to columns present. */
function orderedColumns(columns: string[], targetCol: string): string[] {
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const col of [targetCol, ...columns]) {
    if (col && !seen.has(col)) {
      seen.add(col)
      ordered.push(col)
    }
  }
  return ordered
}

/**
 * Flatten the training chart plus optional re-forecast overlays into one
 * apex-ready list of coloured, role-segmented line series. Each column becomes
 * up to four segments (train / test / test-fit / future) that share the role
 * colours; the target draws thicker. Overlays append the interactive forecast
 * and any supplied known-future values.
 */
export function buildForecastSegments(
  chart: ForecastingChart,
  overlays: ForecastChartOverlays,
): ForecastChartSegment[] {
  const { targetCol, prediction, supplied } = overlays
  const split = chart.split_date
  const segments: ForecastChartSegment[] = []

  for (const col of orderedColumns(Object.keys(chart.series), targetCol)) {
    const series = chart.series[col]
    if (!series) continue
    const width = col === targetCol ? TARGET_WIDTH : SERIES_WIDTH
    const { train, test } = splitActuals(series.actuals, split)

    if (train.length)
      segments.push(
        segment(col, 'train', FORECAST_SEGMENT_COLORS.train, DASH_SOLID, width, 0, train),
      )
    if (test.length)
      segments.push(segment(col, 'test', FORECAST_SEGMENT_COLORS.test, DASH_SOLID, width, 0, test))
    if (series.test_fit?.length) {
      segments.push(
        segment(
          col,
          'testFit',
          FORECAST_SEGMENT_COLORS.testFit,
          DASH_DASHED,
          width,
          FIT_MARKER_SIZE,
          series.test_fit,
        ),
        ...boundSegments(col, 'testFit', FORECAST_SEGMENT_COLORS.testFit, series.test_fit),
      )
    }
    if (series.future?.length) {
      segments.push(
        segment(
          col,
          'future',
          FORECAST_SEGMENT_COLORS.forecast,
          DASH_DASHED,
          width,
          0,
          series.future,
        ),
        ...boundSegments(col, 'future', FORECAST_SEGMENT_COLORS.forecast, series.future),
      )
    }
  }

  if (prediction) {
    for (const col of orderedColumns(Object.keys(prediction), targetCol)) {
      const points = prediction[col]
      if (!points?.length) continue
      const width = col === targetCol ? TARGET_WIDTH : SERIES_WIDTH
      segments.push(
        segment(col, 'prediction', FORECAST_SEGMENT_COLORS.forecast, DASH_DASHED, width, 3, points),
        ...boundSegments(col, 'prediction', FORECAST_SEGMENT_COLORS.forecast, points),
      )
    }
  }

  if (supplied) {
    for (const col of Object.keys(supplied)) {
      const points = supplied[col]
      if (!points?.length) continue
      segments.push(
        segment(
          col,
          'supplied',
          FORECAST_SEGMENT_COLORS.test,
          DASH_DOTTED,
          SERIES_WIDTH,
          4,
          points,
        ),
      )
    }
  }

  return segments
}
