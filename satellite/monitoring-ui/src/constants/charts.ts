export interface ChartMeta {
  title: string
  subtitle: string
  color: string
}

export const CHART_HEIGHT = 200

export const DEFAULT_CHART_COLOR = '--p-primary-color'

export const SERIES_CHART_META: Record<string, ChartMeta> = {
  requests: {
    title: 'Requests over time',
    subtitle: 'prediction calls per interval',
    color: '--p-primary-color',
  },
  error_rate: {
    title: 'Error rate over time',
    subtitle: '4xx / 5xx share of calls',
    color: '--p-red-500',
  },
  latency_p95: {
    title: 'Latency p95 over time',
    subtitle: '95th percentile response time',
    color: '--p-orange-500',
  },
}
