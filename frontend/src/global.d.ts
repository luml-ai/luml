import type { AnalyticsInterface } from './lib/analytics/AnalyticsService'

export {}

declare global {
  interface Window {
    analytics: AnalyticsInterface
  }
}
