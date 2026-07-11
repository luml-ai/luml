import type { AnalyticsInterface } from './lib/analytics/AnalyticsService'

export {}

declare global {
  interface Window {
    pyodideWorker: Worker
    pyodideStartedLoading: boolean
    analytics: AnalyticsInterface
  }
}
