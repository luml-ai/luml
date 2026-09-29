export enum MonitoringIneligibilityReason {
  monitoring_off = 'monitoring_off',
  capability_missing = 'capability_missing',
  capability_version_unsupported = 'capability_version_unsupported',
  no_dashboard_address = 'no_dashboard_address',
}

export interface MonitoringEligibility {
  eligible: boolean
  satellite_base_url: string | null
  reason: MonitoringIneligibilityReason | null
}

export interface MonitoringLaunchToken {
  token: string
  satellite_base_url: string | null
  launch_url?: string
  expires_at: number
}
