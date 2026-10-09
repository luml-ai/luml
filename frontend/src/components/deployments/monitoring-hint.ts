import { MonitoringFeature } from '@/lib/api/satellites/interfaces'

const TABULAR_KIND_TAG = 'luml.ai::kind_tabular:v1'
const TABULAR_MONITORING_TAG = 'luml.ai::tabular_monitoring:v1'

const UNIVERSAL_FEATURES = [
  MonitoringFeature.runtime,
  MonitoringFeature.traces,
  MonitoringFeature.alerts,
]

const PROFILE_DEPENDENT_FEATURES = new Set([
  MonitoringFeature.data_quality,
  MonitoringFeature.feature_drift,
  MonitoringFeature.output_drift,
  MonitoringFeature.multivariate_drift,
])

const FEATURE_LABELS: Record<MonitoringFeature, string> = {
  [MonitoringFeature.runtime]: 'Runtime',
  [MonitoringFeature.traces]: 'Traces',
  [MonitoringFeature.alerts]: 'Alerts',
  [MonitoringFeature.data_quality]: 'Data quality',
  [MonitoringFeature.feature_drift]: 'Feature drift',
  [MonitoringFeature.output_drift]: 'Output drift',
  [MonitoringFeature.multivariate_drift]: 'Multivariate drift',
}

export interface MonitoringHint {
  sectionLabels: string[]
  recommendRepack: boolean
}

export function getMonitoringHint(
  producerTags: readonly string[],
  advertisedFeatures: readonly MonitoringFeature[],
): MonitoringHint {
  const hasSupportedProfile = producerTags.includes(TABULAR_MONITORING_TAG)
  const features = hasSupportedProfile
    ? [
        ...UNIVERSAL_FEATURES,
        ...advertisedFeatures.filter((feature) => PROFILE_DEPENDENT_FEATURES.has(feature)),
      ]
    : UNIVERSAL_FEATURES

  return {
    sectionLabels: [...new Set(features)].map((feature) => FEATURE_LABELS[feature]),
    recommendRepack: producerTags.includes(TABULAR_KIND_TAG) && !hasSupportedProfile,
  }
}
