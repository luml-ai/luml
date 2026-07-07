import { api } from '@/lib/api'
import {
  MonitoringIneligibilityReason,
  type MonitoringEligibility,
  type MonitoringLaunchToken,
} from '@/lib/api/monitoring/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * postMessage type the Satellite-served dashboard SPA emits when its session
 * expires (Query API 401), so the Platform can surface a re-launch action.
 */
export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

export type MonitoringLaunchStatus =
  | 'idle'
  | 'loading'
  | 'disabled'
  | 'unavailable'
  | 'active'
  | 'expired'

export const useMonitoringStore = defineStore('monitoring', () => {
  const status = ref<MonitoringLaunchStatus>('idle')
  const eligibility = ref<MonitoringEligibility | null>(null)
  const launchToken = ref<MonitoringLaunchToken | null>(null)
  const reason = ref<MonitoringIneligibilityReason | null>(null)

  const launchUrl = computed(() => {
    if (!launchToken.value) return null
    const base = launchToken.value.satellite_base_url.replace(/\/$/, '')
    return `${base}/monitoring/launch?token=${encodeURIComponent(launchToken.value.token)}`
  })

  const satelliteOrigin = computed(() => {
    const url = launchToken.value?.satellite_base_url
    if (!url) return null
    try {
      return new URL(url).origin
    } catch {
      return null
    }
  })

  async function launch(organizationId: string, orbitId: string, deploymentId: string) {
    status.value = 'loading'
    reason.value = null
    launchToken.value = null
    try {
      const result = await api.monitoring.getEligibility(organizationId, orbitId, deploymentId)
      eligibility.value = result
      if (!result.eligible) {
        reason.value = result.reason ?? MonitoringIneligibilityReason.monitoring_off
        status.value = 'disabled'
        return
      }
      launchToken.value = await api.monitoring.mintLaunchToken(
        organizationId,
        orbitId,
        deploymentId,
      )
      status.value = 'active'
    } catch {
      status.value = 'unavailable'
    }
  }

  function markExpired() {
    if (status.value === 'active') {
      status.value = 'expired'
    }
  }

  function reset() {
    status.value = 'idle'
    eligibility.value = null
    launchToken.value = null
    reason.value = null
  }

  return {
    status,
    eligibility,
    launchToken,
    reason,
    launchUrl,
    satelliteOrigin,
    launch,
    markExpired,
    reset,
  }
})
