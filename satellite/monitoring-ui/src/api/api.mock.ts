import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import {
  Compare,
  ProfileStatus,
  SectionState,
  Severity,
  SeverityFilter,
  SpanTypeEnum,
  Window,
  type AlertBanner,
  type AlertsResponse,
  type Card,
  type DataQualityFeatureRow,
  type DataQualityResponse,
  type DriftedFeature,
  type FeatureDistribution,
  type FeatureDriftDetail,
  type FeatureDriftResponse,
  type HeaderResponse,
  type OutputDriftResponse,
  type OverviewResponse,
  type PcaPoint,
  type ReferenceProfileFeature,
  type ReferenceProfileResponse,
  type RuntimeResponse,
  type Series,
  type SeriesPoint,
  type SessionInfo,
  type SortOrder,
  type TraceDetail,
  type TraceDetailResponse,
  type TraceRow,
  type TraceSortKey,
  type TraceSpan,
  type TracesResponse,
  type WorkerHealthResponse,
} from './monitoring/interfaces'

type MockParams = Record<string, string | undefined>

interface MockRequest {
  path: string
  params: MockParams
  body: Record<string, unknown>
}

type MockHandler = (request: MockRequest) => unknown

interface MockDims {
  window: Window
  compare: Compare
  severity: SeverityFilter
  feature: string | null
  start: Date | null
  end: Date | null
}

const DEPLOYMENT_ID = 'mock-deployment-1'
const MOCK_DELAY_MS = 350
const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

const WINDOW_MS: Record<Window, number> = {
  [Window.H24]: DAY_MS,
  [Window.D7]: 7 * DAY_MS,
  [Window.D30]: 30 * DAY_MS,
}

interface MockFeature {
  name: string
  kind: 'numeric' | 'categorical'
  psi: number
  missingRate: number
  typeErrorRate: number
  rangeRate: number
  categories?: string[]
  min?: number
  max?: number
}

const FEATURES: MockFeature[] = [
  {
    name: 'age',
    kind: 'numeric',
    psi: 0.04,
    missingRate: 0.001,
    typeErrorRate: 0,
    rangeRate: 0.02,
    min: 18,
    max: 64,
  },
  {
    name: 'bmi',
    kind: 'numeric',
    psi: 0.14,
    missingRate: 0.012,
    typeErrorRate: 0.002,
    rangeRate: 0.01,
    min: 15.9,
    max: 53.1,
  },
  {
    name: 'children',
    kind: 'numeric',
    psi: 0.02,
    missingRate: 0,
    typeErrorRate: 0,
    rangeRate: 0,
    min: 0,
    max: 5,
  },
  {
    name: 'smoker',
    kind: 'categorical',
    psi: 0.31,
    missingRate: 0.004,
    typeErrorRate: 0,
    rangeRate: 0,
    categories: ['no', 'yes'],
  },
  {
    name: 'region',
    kind: 'categorical',
    psi: 0.09,
    missingRate: 0.2,
    typeErrorRate: 0.05,
    rangeRate: 0.1,
    categories: ['northeast', 'northwest', 'southeast', 'southwest'],
  },
  {
    name: 'sex',
    kind: 'categorical',
    psi: 0.01,
    missingRate: 0,
    typeErrorRate: 0,
    rangeRate: 0,
    categories: ['female', 'male'],
  },
]

const acknowledged = new Set<string>()

const seeded = (seed: number) => {
  let state = seed % 2147483647
  if (state <= 0) state += 2147483646
  return () => {
    state = (state * 16807) % 2147483647
    return (state - 1) / 2147483646
  }
}

const hash = (value: string) => {
  let result = 0
  for (const char of value) result = (result * 31 + char.charCodeAt(0)) | 0
  return Math.abs(result) + 1
}

const round = (value: number, digits = 4) => Number(value.toFixed(digits))

const severityFor = (value: number, warning: number, critical: number) =>
  value >= critical ? Severity.CRITICAL : value >= warning ? Severity.WARNING : Severity.OK

const parseDate = (value: string | undefined) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const parseDims = (params: MockParams): MockDims => ({
  window: Object.values(Window).includes(params.window as Window)
    ? (params.window as Window)
    : Window.H24,
  compare: Object.values(Compare).includes(params.compare as Compare)
    ? (params.compare as Compare)
    : Compare.REFERENCE,
  severity: Object.values(SeverityFilter).includes(params.severity as SeverityFilter)
    ? (params.severity as SeverityFilter)
    : SeverityFilter.ALL,
  feature: params.feature ?? null,
  start: parseDate(params.start),
  end: parseDate(params.end),
})

const nowHour = () => {
  const now = new Date()
  now.setMinutes(0, 0, 0)
  return now
}

const timeline = (dims: MockDims) => {
  const end = dims.end ?? nowHour()
  const start = dims.start ?? new Date(end.getTime() - WINDOW_MS[dims.window])
  const span = Math.max(end.getTime() - start.getTime(), HOUR_MS)
  const step = span > 2 * DAY_MS ? DAY_MS : HOUR_MS
  const count = Math.max(Math.round(span / step), 2)
  return Array.from({ length: count }, (_, index) =>
    new Date(end.getTime() - (count - 1 - index) * step).toISOString(),
  )
}

const makePoints = (
  times: string[],
  seed: string,
  base: number,
  amplitude: number,
  digits = 4,
): SeriesPoint[] => {
  const random = seeded(hash(seed))
  return times.map((t, index) => ({
    t,
    value: round(
      Math.max(base + Math.sin(index / 3) * amplitude * 0.5 + (random() - 0.5) * amplitude, 0),
      digits,
    ),
  }))
}

const makeSeries = (
  dims: MockDims,
  key: string,
  label: string,
  base: number,
  amplitude: number,
  unit: string | null = null,
  digits = 4,
): Series => {
  const times = timeline(dims)
  return {
    key,
    label,
    unit,
    points: makePoints(times, `${key}:${dims.window}`, base, amplitude, digits),
    baseline:
      dims.compare === Compare.OFF
        ? null
        : makePoints(times, `${key}:${dims.window}:baseline`, base * 0.92, amplitude * 0.6, digits),
  }
}

const filterBySeverity = (alerts: AlertBanner[], filter: SeverityFilter) => {
  const visible = alerts.filter((alert) => !acknowledged.has(alert.metric))
  if (filter === SeverityFilter.ALL) return visible
  if (filter === SeverityFilter.CRITICAL)
    return visible.filter((alert) => alert.severity === Severity.CRITICAL)
  return visible.filter((alert) => alert.severity !== Severity.OK)
}

const featureAlert = (dims: MockDims, feature: MockFeature): AlertBanner => {
  const severity = severityFor(feature.psi, 0.1, 0.25)
  const threshold = severity === Severity.CRITICAL ? 0.25 : 0.1
  return {
    group: 'feature_drift',
    metric: `feature_drift:psi:${feature.name}`,
    feature: feature.name,
    severity,
    current_value: feature.psi,
    threshold,
    message: `PSI ${feature.psi.toFixed(2)} vs threshold ${threshold}`,
    first_seen: new Date(nowHour().getTime() - 6 * HOUR_MS).toISOString(),
    last_seen: nowHour().toISOString(),
    label: 'PSI',
    unit: 'score',
    value_label: feature.psi.toFixed(2),
    threshold_label: String(threshold),
    state: 'open',
    duration_seconds: 6 * 3600,
    threshold_source: 'default',
    history: makeSeries(
      dims,
      `psi_${feature.name}`,
      `PSI · ${feature.name}`,
      feature.psi,
      0.08,
      'score',
    ),
  }
}

const allAlerts = (dims: MockDims): AlertBanner[] => [
  ...FEATURES.filter((feature) => feature.psi >= 0.1).map((feature) => featureAlert(dims, feature)),
  {
    group: 'runtime',
    metric: 'runtime:latency_p95',
    feature: null,
    severity: Severity.WARNING,
    current_value: 412,
    threshold: 400,
    message: 'Latency p95 412 ms vs threshold 400 ms',
    first_seen: new Date(nowHour().getTime() - 2 * HOUR_MS).toISOString(),
    last_seen: nowHour().toISOString(),
    label: 'Latency p95',
    unit: 'ms',
    value_label: '412 ms',
    threshold_label: '400 ms',
    state: 'open',
    duration_seconds: 2 * 3600,
    threshold_source: 'custom',
    history: makeSeries(dims, 'latency_p95', 'Latency p95', 380, 80, 'ms', 0),
  },
  {
    group: 'data_quality',
    metric: 'data_quality:missing_rate:region',
    feature: 'region',
    severity: Severity.CRITICAL,
    current_value: 0.2,
    threshold: 0.05,
    message: 'Missing rate 20% vs threshold 5%',
    first_seen: new Date(nowHour().getTime() - 12 * HOUR_MS).toISOString(),
    last_seen: nowHour().toISOString(),
    label: 'Missing rate',
    unit: 'ratio',
    value_label: '20%',
    threshold_label: '5%',
    state: 'open',
    duration_seconds: 12 * 3600,
    threshold_source: 'default',
    history: makeSeries(dims, 'missing_region', 'Missing rate · region', 0.18, 0.06, 'ratio'),
  },
  {
    group: 'output_drift',
    metric: 'output_drift:prediction',
    feature: null,
    severity: Severity.CRITICAL,
    current_value: 0.42,
    threshold: 0.25,
    message: 'PSI 0.42 vs threshold 0.25',
    first_seen: new Date(nowHour().getTime() - 4 * HOUR_MS).toISOString(),
    last_seen: nowHour().toISOString(),
    label: 'PSI',
    unit: 'score',
    value_label: '0.42',
    threshold_label: '0.25',
    state: 'open',
    duration_seconds: 4 * 3600,
    threshold_source: 'default',
    history: makeSeries(dims, 'output_psi', 'Output PSI', 0.38, 0.1, 'score'),
  },
]

const driftedFeatures = (dims: MockDims): DriftedFeature[] =>
  [...FEATURES]
    .sort((a, b) => b.psi - a.psi)
    .map((feature) => ({
      feature: feature.name,
      psi: feature.psi,
      severity: severityFor(feature.psi, 0.1, 0.25),
      baseline_psi: dims.compare === Compare.OFF ? null : round(feature.psi * 0.7),
      psi_delta: dims.compare === Compare.OFF ? null : round(feature.psi * 0.3),
    }))

const distributionFor = (feature: MockFeature): FeatureDistribution => {
  const random = seeded(hash(`dist:${feature.name}`))
  const labels =
    feature.kind === 'categorical'
      ? (feature.categories ?? [])
      : Array.from({ length: 10 }, (_, index) => {
          const min = feature.min ?? 0
          const step = ((feature.max ?? 1) - min) / 10
          return `[${round(min + index * step, 1)}, ${round(min + (index + 1) * step, 1)})`
        })
  const reference = labels.map(() => random() + 0.2)
  const current = reference.map((value) =>
    Math.max(value + (random() - 0.5) * feature.psi * 4, 0.05),
  )
  const total = (values: number[]) => values.reduce((sum, value) => sum + value, 0)
  const referenceTotal = total(reference)
  const currentTotal = total(current)
  return {
    kind: feature.kind,
    bins: labels.map((label, index) => ({
      label,
      reference: round((reference[index] ?? 0) / referenceTotal),
      current: round((current[index] ?? 0) / currentTotal),
    })),
  }
}

const findFeature = (name: string | null): MockFeature =>
  FEATURES.find((feature) => feature.name === name) ?? (FEATURES[0] as MockFeature)

const ellipse = (cx: number, cy: number, rx: number, ry: number): PcaPoint[] =>
  Array.from({ length: 33 }, (_, index) => {
    const angle = (index / 32) * Math.PI * 2
    return { x: round(cx + Math.cos(angle) * rx, 3), y: round(cy + Math.sin(angle) * ry, 3) }
  })

const cloud = (seed: string, cx: number, cy: number, spread: number, count: number): PcaPoint[] => {
  const random = seeded(hash(seed))
  return Array.from({ length: count }, () => ({
    x: round(cx + (random() + random() - 1) * spread, 3),
    y: round(cy + (random() + random() - 1) * spread * 0.7, 3),
  }))
}

const TRACE_TOTAL = 137

const traceRows = (dims: MockDims): TraceRow[] => {
  const random = seeded(hash(`traces:${dims.window}`))
  const end = (dims.end ?? new Date()).getTime()
  const span = WINDOW_MS[dims.window]
  return Array.from({ length: TRACE_TOTAL }, (_, index) => {
    const roll = random()
    const status = roll > 0.95 ? 'error' : roll > 0.93 ? 'timeout' : 'success'
    const statusCode = status === 'error' ? 500 : status === 'timeout' ? 504 : 200
    const age = Math.round(random() * 40)
    return {
      event_id: `evt-${String(index + 1).padStart(5, '0')}`,
      ts: new Date(end - (index / TRACE_TOTAL) * span - random() * 60_000).toISOString(),
      features_summary: `age=${18 + age}, bmi=${round(18 + random() * 20, 1)}, smoker=${random() > 0.7 ? 'yes' : 'no'}`,
      prediction: status === 'success' ? round(2000 + random() * 40000, 2).toString() : null,
      latency_ms: Math.round(status === 'timeout' ? 5000 : 30 + random() * 400),
      status,
      status_code: statusCode,
    }
  })
}

const sortRows = (rows: TraceRow[], sort: TraceSortKey, order: SortOrder) => {
  const direction = order === 'asc' ? 1 : -1
  const value = (row: TraceRow) =>
    sort === 'latency' ? row.latency_ms : sort === 'status' ? row.status : row.ts
  return [...rows].sort((a, b) =>
    value(a) > value(b) ? direction : value(a) < value(b) ? -direction : 0,
  )
}

const traceSpans = (row: TraceRow): TraceSpan[] => {
  const traceId = `trace-${row.event_id}`
  const start = new Date(row.ts).getTime() * 1_000_000
  const total = row.latency_ms * 1_000_000
  const span = (
    id: string,
    parent: string | null,
    name: string,
    from: number,
    to: number,
    type: SpanTypeEnum,
    attributes: Record<string, unknown>,
  ): TraceSpan => ({
    trace_id: traceId,
    span_id: id,
    parent_span_id: parent,
    name,
    kind: 1,
    start_time_unix_nano: start + Math.round(total * from),
    end_time_unix_nano: start + Math.round(total * to),
    status_code: row.status === 'success' ? 1 : 2,
    status_message: row.status === 'success' ? null : `${row.status} (${row.status_code})`,
    attributes,
    events: [],
    links: [],
    dfs_span_type: type,
    annotation_count: 0,
  })
  return [
    span('span-root', null, 'POST /compute', 0, 1, SpanTypeEnum.DEFAULT, {
      'http.method': 'POST',
      'http.status_code': row.status_code,
    }),
    span('span-validate', 'span-root', 'validate_inputs', 0.02, 0.12, SpanTypeEnum.DEFAULT, {
      features: FEATURES.length,
    }),
    span('span-predict', 'span-root', 'model.predict', 0.15, 0.9, SpanTypeEnum.DEFAULT, {
      model: 'v3',
      batch_size: 1,
    }),
    span('span-serialize', 'span-root', 'serialize_output', 0.9, 0.98, SpanTypeEnum.DEFAULT, {}),
  ]
}

const header = (): HeaderResponse => ({
  state: SectionState.OK,
  deployment_id: DEPLOYMENT_ID,
  name: 'insurance-charges-regressor',
  status: 'Active',
  task_type: 'Tabular Regression',
  model_kind: 'tabular',
  model_name: 'v3',
  environment: 'production',
  satellite: 'eu-west-sat-2',
  inference_url: 'https://sat.example.com/deployments/mock-deployment-1/compute',
  last_prediction_at: new Date(Date.now() - 45_000).toISOString(),
  last_monitored_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  profile_status: ProfileStatus.READY,
})

const overview = (dims: MockDims): OverviewResponse => {
  const alerts = filterBySeverity(allAlerts(dims), dims.severity)
  const drifted = driftedFeatures(dims).filter((feature) => feature.severity !== Severity.OK)
  const delta = dims.compare === Compare.OFF ? null : dims.compare
  const cards: Card[] = [
    {
      key: 'requests',
      label: 'Requests',
      value: 12430,
      delta: delta ? 340 : null,
      delta_kind: delta,
    },
    {
      key: 'error_rate',
      label: 'Error rate',
      value: 0.0484,
      unit: 'ratio',
      delta: delta ? 0.006 : null,
      delta_kind: delta,
      severity: Severity.WARNING,
    },
    {
      key: 'latency_p95',
      label: 'Latency p95',
      value: 412,
      unit: 'ms',
      delta: delta ? 38 : null,
      delta_kind: delta,
      severity: Severity.WARNING,
    },
    {
      key: 'active_alerts',
      label: 'Active alerts',
      value: alerts.length,
      critical_count: alerts.filter((alert) => alert.severity === Severity.CRITICAL).length,
      severity: alerts.some((alert) => alert.severity === Severity.CRITICAL)
        ? Severity.CRITICAL
        : Severity.OK,
    },
    {
      key: 'drifted_features',
      label: 'Drifted features',
      value: drifted.length,
      feature_names: drifted.map((feature) => feature.feature),
      severity: drifted.length ? Severity.WARNING : Severity.OK,
    },
  ]
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    cards,
    alert_banners: alerts,
    series: [
      makeSeries(dims, 'requests', 'Requests', 520, 180, null, 0),
      makeSeries(dims, 'error_rate', 'Error rate', 0.045, 0.03, 'ratio'),
      makeSeries(dims, 'latency_p95', 'Latency p95', 380, 90, 'ms', 0),
    ],
    top_drifted_features: driftedFeatures(dims).slice(0, 5),
  }
}

const runtime = (dims: MockDims): RuntimeResponse => ({
  state: SectionState.OK,
  profile_status: ProfileStatus.READY,
  request_count: 12430,
  success_count: 11828,
  success_rate: 0.9516,
  error_count: 602,
  error_rate: 0.0484,
  latency_p50_ms: 42,
  latency_p95_ms: 412,
  latency_max_ms: 5000,
  timeout_count: 31,
  failed_inference_count: 120,
  status_breakdown: [
    { status: 'success', status_code: 200, count: 11828, share: 0.9516 },
    { status: 'error', status_code: 422, count: 451, share: 0.0363 },
    { status: 'failed_inference', status_code: 500, count: 120, share: 0.0097 },
    { status: 'timeout', status_code: 504, count: 31, share: 0.0024 },
  ],
  baseline:
    dims.compare === Compare.OFF
      ? null
      : {
          start: new Date(nowHour().getTime() - 2 * WINDOW_MS[dims.window]).toISOString(),
          end: new Date(nowHour().getTime() - WINDOW_MS[dims.window]).toISOString(),
          request_count: 12090,
          success_rate: 0.9602,
          error_rate: 0.0398,
          latency_p50_ms: 40,
          latency_p95_ms: 374,
          latency_max_ms: 4200,
          timeout_count: 22,
          failed_inference_count: 98,
        },
  series: [
    makeSeries(dims, 'requests', 'Requests', 520, 180, null, 0),
    makeSeries(dims, 'error_rate', 'Error rate', 0.045, 0.03, 'ratio'),
    makeSeries(dims, 'latency_p50', 'Latency p50', 42, 12, 'ms', 0),
    makeSeries(dims, 'latency_p95', 'Latency p95', 380, 90, 'ms', 0),
  ],
  alerts: filterBySeverity(allAlerts(dims), dims.severity).filter(
    (alert) => alert.group === 'runtime',
  ),
})

const dataQualityRow = (feature: MockFeature): DataQualityFeatureRow => {
  const checked = 12430
  const worst = Math.max(feature.missingRate, feature.typeErrorRate, feature.rangeRate)
  const unseen = feature.kind === 'categorical' ? feature.rangeRate : 0
  return {
    feature: feature.name,
    kind: feature.kind,
    missing_rate: feature.missingRate,
    type_error_rate: feature.typeErrorRate,
    range_unseen_rate: feature.rangeRate,
    range_violation_rate: feature.kind === 'numeric' ? feature.rangeRate : null,
    unseen_category_rate: feature.kind === 'categorical' ? unseen : null,
    checked,
    status: severityFor(worst, 0.02, 0.1),
    missing_delta: round(feature.missingRate * 0.2),
    type_error_delta: round(feature.typeErrorRate * 0.1),
    range_unseen_delta: round(feature.rangeRate * 0.15),
    invalid: {
      missing_count: Math.round(checked * feature.missingRate),
      type_mismatch_count: Math.round(checked * feature.typeErrorRate),
      observed_types: feature.typeErrorRate
        ? { int: Math.round(checked * feature.typeErrorRate) }
        : {},
      type_examples: feature.typeErrorRate ? ['7', '42'] : [],
      range_violation_count:
        feature.kind === 'numeric' ? Math.round(checked * feature.rangeRate) : 0,
      below_min: feature.kind === 'numeric' ? Math.round(checked * feature.rangeRate * 0.3) : 0,
      above_max: feature.kind === 'numeric' ? Math.round(checked * feature.rangeRate * 0.7) : 0,
      observed_min: feature.min !== undefined ? round(feature.min * 0.8, 1) : null,
      observed_max: feature.max !== undefined ? round(feature.max * 1.4, 1) : null,
      reference_min: feature.min ?? null,
      reference_max: feature.max ?? null,
      unseen_category_count: Math.round(checked * unseen),
      unseen_distinct: unseen ? 2 : 0,
      reference_categories: feature.categories?.length ?? null,
      unseen_categories: unseen
        ? [
            { value: 'antarctica', count: Math.round(checked * unseen * 0.84) },
            { value: 'mars', count: Math.round(checked * unseen * 0.16) },
          ]
        : [],
    },
  }
}

const dataQuality = (dims: MockDims): DataQualityResponse => ({
  state: SectionState.OK,
  profile_status: ProfileStatus.READY,
  features: FEATURES.map(dataQualityRow),
  trends: [
    makeSeries(dims, 'missing_rate', 'Missing rate', 0.03, 0.02, 'ratio'),
    makeSeries(dims, 'type_error_rate', 'Type error rate', 0.008, 0.006, 'ratio'),
    makeSeries(dims, 'range_unseen_rate', 'Out of range / unseen', 0.02, 0.015, 'ratio'),
  ],
  alerts: filterBySeverity(allAlerts(dims), dims.severity).filter(
    (alert) => alert.group === 'data_quality',
  ),
  computed_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  stale: false,
})

const featureDriftDetail = (dims: MockDims, feature: MockFeature): FeatureDriftDetail => ({
  feature: feature.name,
  psi: feature.psi,
  status: severityFor(feature.psi, 0.1, 0.25),
  distribution: distributionFor(feature),
  psi_over_time: makeSeries(
    dims,
    `psi_${feature.name}`,
    `PSI · ${feature.name}`,
    feature.psi,
    0.08,
    'score',
  ),
})

const featureDrift = (dims: MockDims): FeatureDriftResponse => {
  const features = driftedFeatures(dims)
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    features,
    selected: featureDriftDetail(dims, findFeature(dims.feature ?? features[0]?.feature ?? null)),
    multivariate: {
      state: SectionState.OK,
      status: Severity.WARNING,
      shift_value: 3.4,
      shift_metric: 'mahalanobis',
      shift_unit: 'σ',
      dispersion_ratio: 1.18,
      outlier_rate: 0.034,
      reference_ellipse: ellipse(0, 0, 1.6, 1.1),
      current_ellipse: ellipse(0.8, 0.4, 1.9, 1.2),
      explained_variance: [0.48, 0.27, 0.14, 0.11],
      feature_psi: features,
      reference_projection: cloud('pca:reference', 0, 0, 1.6, 150),
      current_projection: cloud('pca:current', 0.8, 0.4, 1.9, 150),
    },
    alerts: filterBySeverity(allAlerts(dims), dims.severity).filter(
      (alert) => alert.group === 'feature_drift',
    ),
    computed_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    stale: false,
  }
}

const outputDrift = (dims: MockDims): OutputDriftResponse => ({
  state: SectionState.OK,
  profile_status: ProfileStatus.READY,
  name: 'charges',
  kind: 'numeric',
  psi: 0.42,
  baseline_psi: dims.compare === Compare.OFF ? null : 0.18,
  psi_delta: dims.compare === Compare.OFF ? null : 0.24,
  severity: Severity.CRITICAL,
  count: 11828,
  distribution: distributionFor({
    name: 'charges',
    kind: 'numeric',
    psi: 0.42,
    missingRate: 0,
    typeErrorRate: 0,
    rangeRate: 0,
    min: 1100,
    max: 63800,
  }),
  psi_over_time: makeSeries(dims, 'output_psi', 'PSI', 0.38, 0.12, 'score'),
  trend: [
    makeSeries(dims, 'prediction_mean', 'Mean', 13800, 1500, null, 0),
    makeSeries(dims, 'prediction_median', 'Median', 9400, 1200, null, 0),
    makeSeries(dims, 'prediction_p05', 'p05', 1900, 400, null, 0),
    makeSeries(dims, 'prediction_p95', 'p95', 41000, 4000, null, 0),
  ],
  top_changed: [],
  class_share_trend: [],
  confidence: null,
  probabilities: null,
  horizons: [],
  alerts: filterBySeverity(allAlerts(dims), dims.severity).filter(
    (alert) => alert.group === 'output_drift',
  ),
  computed_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  stale: false,
})

const referenceFeature = (feature: MockFeature): ReferenceProfileFeature => {
  const distribution = distributionFor(feature)
  if (feature.kind === 'categorical') {
    return {
      feature: feature.name,
      kind: 'categorical',
      summary: { unique: feature.categories?.length ?? 0, missing_rate: feature.missingRate },
      categories: distribution.bins.map((bin) => bin.label),
      category_probabilities: distribution.bins.map((bin) => bin.reference ?? 0),
    }
  }
  const min = feature.min ?? 0
  const max = feature.max ?? 1
  const step = (max - min) / distribution.bins.length
  return {
    feature: feature.name,
    kind: 'numeric',
    summary: {
      mean: round((min + max) / 2, 2),
      std: round((max - min) / 5, 2),
      min,
      max,
      missing_rate: feature.missingRate,
    },
    bin_edges: Array.from({ length: distribution.bins.length + 1 }, (_, index) =>
      round(min + index * step, 2),
    ),
    histogram: distribution.bins.map((bin) => bin.reference ?? 0),
  }
}

const referenceProfile = (dims: MockDims): ReferenceProfileResponse => {
  const feature = findFeature(dims.feature)
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    baseline_label: 'training set (2026-01-05)',
    computed_at: '2026-01-05T12:00:00Z',
    features: FEATURES.map((item) => item.name),
    feature: referenceFeature(feature),
    document: {
      profile_status: 'ready',
      task_type: 'regression',
      n_reference_samples: 1070,
      feature_summaries: {
        numerical_features: Object.fromEntries(
          FEATURES.filter((item) => item.kind === 'numeric').map((item) => [
            item.name,
            { min: item.min, max: item.max },
          ]),
        ),
        categorical_features: Object.fromEntries(
          FEATURES.filter((item) => item.kind === 'categorical').map((item) => [
            item.name,
            { categories: item.categories },
          ]),
        ),
      },
      output_summary: { name: 'charges', type: 'numerical' },
      pca_profile: { pca: { explained_variance_ratio: [0.48, 0.27, 0.14, 0.11] } },
    },
  }
}

const alerts = (dims: MockDims): AlertsResponse => {
  const visible = filterBySeverity(allAlerts(dims), dims.severity)
  const groups = [...new Set(visible.map((alert) => alert.group))]
  return {
    state: visible.length ? SectionState.OK : SectionState.EMPTY,
    profile_status: ProfileStatus.READY,
    groups: groups.map((group) => ({
      group,
      alerts: visible.filter((alert) => alert.group === group),
    })),
  }
}

const workerHealth = (): WorkerHealthResponse => ({
  state: SectionState.OK,
  running: true,
  recording: { state: 'recording', reason: null },
  last_tick_at: new Date(Date.now() - 30_000).toISOString(),
  windows_processed: 1284,
  last_window_end: new Date(Date.now() - 5 * 60_000).toISOString(),
  last_lag_seconds: 18,
  window_seconds: 300,
  interval_seconds: 60,
  failures: [
    {
      metric: 'multivariate_drift',
      error: 'not enough samples in window (12 < 50)',
      at: new Date(Date.now() - 3 * HOUR_MS).toISOString(),
    },
  ],
  incidents: [
    {
      metric: 'multivariate_drift',
      error: 'not enough samples in window (12 < 50)',
      started_at: new Date(Date.now() - 3 * HOUR_MS).toISOString(),
      ended_at: new Date(Date.now() - 2 * HOUR_MS).toISOString(),
      ongoing: false,
    },
  ],
})

const traces = (dims: MockDims, params: MockParams): TracesResponse => {
  const limit = Number(params.limit ?? 20)
  const offset = Number(params.offset ?? 0)
  const sort = (params.sort as TraceSortKey | undefined) ?? 'ts'
  const order = (params.order as SortOrder | undefined) ?? 'desc'
  const rows = sortRows(traceRows(dims), sort, order)
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    rows: rows.slice(offset, offset + limit),
    total: rows.length,
    limit,
    offset,
  }
}

const traceDetail = (dims: MockDims, eventId: string): TraceDetailResponse => {
  const row = traceRows(dims).find((item) => item.event_id === eventId)
  if (!row) return { state: SectionState.EMPTY, profile_status: ProfileStatus.READY, trace: null }
  const spans = traceSpans(row)
  const trace: TraceDetail = {
    event_id: row.event_id,
    ts: row.ts,
    latency_ms: row.latency_ms,
    status: row.status,
    status_code: row.status_code,
    trace_id: spans[0]?.trace_id ?? null,
    span_id: spans[0]?.span_id ?? null,
    inputs: Object.fromEntries(
      (row.features_summary ?? '').split(', ').map((pair) => pair.split('=') as [string, string]),
    ),
    output: row.prediction === null ? { error: row.status } : { charges: Number(row.prediction) },
    spans,
  }
  return { state: SectionState.OK, profile_status: ProfileStatus.READY, trace }
}

const session = (): SessionInfo => ({ deployment_id: DEPLOYMENT_ID, scope: 'monitoring:read' })

const getRoutes: Record<string, MockHandler> = {
  '/session': () => session(),
  '/header': () => header(),
  '/overview': ({ params }) => overview(parseDims(params)),
  '/runtime': ({ params }) => runtime(parseDims(params)),
  '/data-quality': ({ params }) => dataQuality(parseDims(params)),
  '/feature-drift': ({ params }) => featureDrift(parseDims(params)),
  '/output-drift': ({ params }) => outputDrift(parseDims(params)),
  '/reference-profile': ({ params }) => referenceProfile(parseDims(params)),
  '/alerts': ({ params }) => alerts(parseDims(params)),
  '/worker': () => workerHealth(),
  '/traces': ({ params }) => traces(parseDims(params), params),
}

const postRoutes: Record<string, MockHandler> = {
  '/alerts/acknowledge': ({ params, body }) => {
    if (typeof body.metric === 'string') acknowledged.add(body.metric)
    return alerts(parseDims(params))
  },
}

const resolveHandler = (method: string, path: string): MockHandler | null => {
  if (method === 'post') return postRoutes[path] ?? null
  if (method !== 'get') return null
  const encodedEventId = path.match(/^\/traces\/([^/]+)$/)?.[1]
  if (encodedEventId) {
    const eventId = decodeURIComponent(encodedEventId)
    return ({ params }) => traceDetail(parseDims(params), eventId)
  }
  return getRoutes[path] ?? null
}

const parseBody = (data: unknown): Record<string, unknown> => {
  if (typeof data === 'string' && data) {
    try {
      return JSON.parse(data) as Record<string, unknown>
    } catch {
      return {}
    }
  }
  return data && typeof data === 'object' ? (data as Record<string, unknown>) : {}
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export const mockAdapter: AxiosAdapter = async (config: InternalAxiosRequestConfig) => {
  await delay(MOCK_DELAY_MS)
  const method = (config.method ?? 'get').toLowerCase()
  const path = (config.url ?? '').split('?')[0] ?? ''
  const handler = resolveHandler(method, path)
  const response = (status: number, data: unknown): AxiosResponse => ({
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Not Found',
    headers: {},
    config,
  })
  if (!handler) {
    throw new AxiosError(
      `Mock route not found: ${method.toUpperCase()} ${path}`,
      AxiosError.ERR_BAD_REQUEST,
      config,
      null,
      response(404, { detail: 'Not Found' }),
    )
  }
  const params = (config.params ?? {}) as MockParams
  return response(200, handler({ path, params, body: parseBody(config.data) }))
}

export const resetMockState = () => acknowledged.clear()
