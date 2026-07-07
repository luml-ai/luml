export enum MonitoringIneligibilityReason {
  monitoring_off = 'monitoring_off',
  capability_missing = 'capability_missing',
}

export interface MonitoringEligibility {
  eligible: boolean
  satellite_base_url: string | null
  reason: MonitoringIneligibilityReason | null
}

export interface MonitoringLaunchToken {
  token: string
  satellite_base_url: string
  expires_at: number
}
