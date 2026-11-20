export interface ChartMeta {
  title: string
  subtitle: string
  color: string
}

export const CHART_HEIGHT = 200

export const DEFAULT_CHART_COLOR = '--p-primary-color'

export const MULTI_SERIES_CHART_COLORS = [
  '--p-primary-color',
  '--p-orange-500',
  '--p-green-500',
  '--p-red-500',
  '--p-purple-500',
  '--p-cyan-500',
  '--p-yellow-500',
  '--p-pink-500',
]

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
