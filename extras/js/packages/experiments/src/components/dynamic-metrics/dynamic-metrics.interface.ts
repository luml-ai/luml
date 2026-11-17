import type { ModelInfo } from '@/interfaces/interfaces'

export interface DynamicMetricsProps {
  modelsInfo: Record<string, ModelInfo>
  showTitle?: boolean
}

export type PlotState = 'loading' | 'provisional' | 'final' | 'error'

export interface PlotStatus {
  /** Bucket level of the aggregated data on screen; null when every point is one logged value. */
  level: number | null
  loading: boolean
  /** The first read error of the chart's experiments; shown next to whatever is drawn. */
  error: string | null
  state: PlotState
}
