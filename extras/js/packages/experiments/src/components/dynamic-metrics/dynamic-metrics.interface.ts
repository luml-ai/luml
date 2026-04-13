import type { ModelInfo } from '@experiments/interfaces/interfaces'

export interface DynamicMetricsProps {
  metricsNames: string[]
  modelsInfo: Record<string, ModelInfo>
  showTitle?: boolean
}
