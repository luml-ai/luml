import type { ModelInfo } from '@/interfaces/interfaces'

export interface DynamicMetricsProps {
  metricsNames: string[]
  modelsInfo: Record<string, ModelInfo>
  showTitle?: boolean
}
