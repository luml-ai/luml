import {
  Compare,
  ProfileStatus,
  SectionState,
  Severity,
  type HeaderResponse,
  type OverviewResponse,
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
