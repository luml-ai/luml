import {
  Compare,
  ProfileStatus,
  SectionState,
  Severity,
  type DataQualityResponse,
  type FeatureDriftDetail,
  type FeatureDriftResponse,
  type HeaderResponse,
  type OverviewResponse,
  type ReferenceProfileResponse,
  type TraceDetail,
  type TracesResponse,
} from '@/api/types'

export function makeHeader(overrides: Partial<HeaderResponse> = {}): HeaderResponse {
  return {
    state: SectionState.OK,
    deployment_id: 'deployment-a',
    name: 'tabular_regression_1781778223788',
    status: 'Active',
    task_type: 'Tabular Regression',
    model_name: 'v3',
    environment: 'insurance charges',
    satellite: 'eu-west-sat-2',
    inference_url: 'https://sat.example.com/inference',
    last_prediction_at: '2026-07-07T12:00:00Z',
    last_monitored_at: '2026-07-07T12:00:00Z',
    profile_status: ProfileStatus.READY,
    ...overrides,
  }
}

export function makeOverview(overrides: Partial<OverviewResponse> = {}): OverviewResponse {
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    cards: [
      {
        key: 'requests',
        label: 'Requests',
        value: 12430,
        delta: 340,
        delta_kind: Compare.PREVIOUS,
      },
      { key: 'error_rate', label: 'Error rate', value: 0.003, unit: 'ratio' },
      { key: 'latency_p95', label: 'Latency p95', value: 180, unit: 'ms' },
      { key: 'active_alerts', label: 'Active alerts', value: 2, critical_count: 2 },
      {
        key: 'drifted_features',
        label: 'Drifted features',
        value: 2,
        feature_names: ['smoker', 'bmi'],
      },
    ],
    alert_banners: [
      {
        group: 'feature_drift',
        metric: 'psi',
        feature: 'smoker',
        severity: Severity.CRITICAL,
        current_value: 0.31,
        threshold: 0.25,
        message: 'PSI 0.31 — share of "yes" moved 20.5% → 45%.',
      },
    ],
    series: [
      {
        key: 'requests',
        label: 'Requests',
        points: [
          { t: '2026-07-07T10:00:00Z', value: 100 },
          { t: '2026-07-07T11:00:00Z', value: 120 },
        ],
      },
      {
        key: 'error_rate',
        label: 'Error rate',
        unit: 'ratio',
        points: [{ t: '2026-07-07T10:00:00Z', value: 0.01 }],
      },
      {
        key: 'latency_p95',
        label: 'Latency p95',
        unit: 'ms',
        points: [{ t: '2026-07-07T10:00:00Z', value: 180 }],
      },
    ],
    top_drifted_features: [
      { feature: 'smoker', psi: 0.31, severity: Severity.CRITICAL },
      { feature: 'bmi', psi: 0.12, severity: Severity.WARNING },
    ],
    ...overrides,
  }
}

export function makeDataQuality(overrides: Partial<DataQualityResponse> = {}): DataQualityResponse {
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    features: [
      {
        feature: 'age',
        missing_rate: 0.01,
        type_error_rate: 0.0,
        range_unseen_rate: 0.02,
        status: Severity.OK,
      },
      {
        feature: 'income',
        missing_rate: 0.2,
        type_error_rate: 0.05,
        range_unseen_rate: 0.1,
        status: Severity.CRITICAL,
      },
    ],
    alerts: [],
    ...overrides,
  }
}

export function makeFeatureDriftDetail(
  overrides: Partial<FeatureDriftDetail> = {},
): FeatureDriftDetail {
  return {
    feature: 'income',
    psi: 0.31,
    status: Severity.CRITICAL,
    distribution: {
      kind: 'numeric',
      bins: [
        { label: '[0,10k)', reference: 0.5, current: 0.2 },
        { label: '[10k,20k)', reference: 0.3, current: 0.3 },
        { label: '[20k,inf)', reference: 0.2, current: 0.5 },
      ],
    },
    psi_over_time: {
      key: 'psi',
      label: 'PSI · income',
      points: [
        { t: '2026-07-07T09:00:00Z', value: 0.1 },
        { t: '2026-07-07T10:00:00Z', value: 0.22 },
        { t: '2026-07-07T11:00:00Z', value: 0.31 },
      ],
    },
    ...overrides,
  }
}

export function makeFeatureDrift(
  overrides: Partial<FeatureDriftResponse> = {},
): FeatureDriftResponse {
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    features: [
      { feature: 'income', psi: 0.31, severity: Severity.CRITICAL },
      { feature: 'age', psi: 0.05, severity: Severity.OK },
    ],
    selected: null,
    multivariate: {
      state: SectionState.OK,
      status: Severity.WARNING,
      shift_value: 3.4,
      shift_metric: 'reconstruction_error',
      explained_variance: [0.6, 0.25, 0.15],
      feature_psi: [
        { feature: 'income', psi: 0.31, severity: Severity.CRITICAL },
        { feature: 'age', psi: 0.05, severity: Severity.OK },
      ],
      reference_projection: [
        { x: 0.1, y: 0.2 },
        { x: -0.3, y: 0.4 },
      ],
      current_projection: [
        { x: 1.1, y: 1.2 },
        { x: 0.9, y: -0.4 },
      ],
    },
    alerts: [],
    ...overrides,
  }
}

export function makeReferenceProfile(
  overrides: Partial<ReferenceProfileResponse> = {},
): ReferenceProfileResponse {
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    baseline_label: 'training set (2026-01-05)',
    computed_at: '2026-06-07T12:00:00Z',
    features: ['income', 'region'],
    feature: {
      feature: 'income',
      kind: 'numeric',
      summary: { mean: 52000, std: 12000, min: 10000, max: 200000 },
      bin_edges: [0, 10000, 20000, 200000],
      histogram: [0.5, 0.3, 0.2],
    },
    ...overrides,
  }
}

export function makeTraces(overrides: Partial<TracesResponse> = {}): TracesResponse {
  return {
    state: SectionState.OK,
    profile_status: ProfileStatus.READY,
    rows: [
      {
        event_id: 'evt-100',
        ts: '2026-07-07T11:58:00Z',
        features_summary: 'age=30, income=52000',
        prediction: 'prediction=0.87',
        latency_ms: 12,
        status: 'success',
        status_code: 200,
      },
      {
        event_id: 'evt-200',
        ts: '2026-07-07T11:55:00Z',
        features_summary: 'age=41, income=61000',
        prediction: 'prediction=0.55',
        latency_ms: 18,
        status: 'error',
        status_code: 500,
      },
    ],
    total: 2,
    limit: 20,
    offset: 0,
    ...overrides,
  }
}

/** A two-span trace: the root `inference` call and its nested `model.execute`. */
export function makeTraceDetail(overrides: Partial<TraceDetail> = {}): TraceDetail {
  const start = 1_000_000_000_000_000_000
  return {
    event_id: 'evt-100',
    ts: '2026-07-07T11:58:00Z',
    latency_ms: 36,
    status: 'success',
    status_code: 200,
    trace_id: 'trc-1',
    span_id: 'root',
    inputs: { 'sepal.length': [[6.82]] },
    output: { y_pred: ['Virginica'] },
    spans: [
      {
        trace_id: 'trc-1',
        span_id: 'root',
        parent_span_id: null,
        name: 'inference',
        kind: 1,
        start_time_unix_nano: start,
        end_time_unix_nano: start + 36_000_000,
        status_code: 1,
        status_message: null,
        attributes: {
          'inference.inputs': { 'sepal.length': [[6.82]] },
          'inference.output': { y_pred: ['Virginica'] },
        },
        events: [],
        links: [],
        dfs_span_type: null,
        annotation_count: 0,
      },
      {
        trace_id: 'trc-1',
        span_id: 'child',
        parent_span_id: 'root',
        name: 'model.execute',
        kind: 1,
        start_time_unix_nano: start + 1_000_000,
        end_time_unix_nano: start + 2_000_000,
        status_code: 1,
        status_message: null,
        attributes: {},
        events: [],
        links: [],
        dfs_span_type: null,
        annotation_count: 0,
      },
    ],
    ...overrides,
  }
}
