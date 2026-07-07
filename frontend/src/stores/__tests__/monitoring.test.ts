import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMonitoringStore } from '@/stores/monitoring'
import { api } from '@/lib/api'
import {
  MonitoringIneligibilityReason,
  type MonitoringEligibility,
  type MonitoringLaunchToken,
} from '@/lib/api/monitoring/interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    monitoring: {
      getEligibility: vi.fn(),
      mintLaunchToken: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api, true)

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const DEPLOYMENT = 'deployment-a'

const eligible: MonitoringEligibility = {
  eligible: true,
  satellite_base_url: 'https://sat.example.com',
  reason: null,
}

const token: MonitoringLaunchToken = {
  token: 'header.payload.sig',
  satellite_base_url: 'https://sat.example.com',
  expires_at: 1_800_000_000,
}

describe('monitoring store', () => {
  let store: ReturnType<typeof useMonitoringStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useMonitoringStore()
    vi.clearAllMocks()
  })

  it('starts idle', () => {
    expect(store.status).toBe('idle')
    expect(store.launchUrl).toBeNull()
    expect(store.reason).toBeNull()
  })

  describe('disabled (ineligible)', () => {
    it('is disabled and mints no token when monitoring is off', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce({
        eligible: false,
        satellite_base_url: null,
        reason: MonitoringIneligibilityReason.monitoring_off,
      })

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('disabled')
      expect(store.reason).toBe(MonitoringIneligibilityReason.monitoring_off)
      expect(store.launchUrl).toBeNull()
      expect(mockApi.monitoring.mintLaunchToken).not.toHaveBeenCalled()
    })

    it('is disabled when the Satellite lacks the capability', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce({
        eligible: false,
        satellite_base_url: null,
        reason: MonitoringIneligibilityReason.capability_missing,
      })

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('disabled')
      expect(store.reason).toBe(MonitoringIneligibilityReason.capability_missing)
      expect(mockApi.monitoring.mintLaunchToken).not.toHaveBeenCalled()
    })

    it('defaults the reason when the API omits it', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce({
        eligible: false,
        satellite_base_url: null,
        reason: null,
      })

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('disabled')
      expect(store.reason).toBe(MonitoringIneligibilityReason.monitoring_off)
    })
  })

  describe('active (eligible)', () => {
    it('mints a token and builds the launch URL with the token', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce(token)

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('active')
      expect(store.launchToken).toEqual(token)
      expect(store.launchUrl).toBe(
        'https://sat.example.com/monitoring/launch?token=header.payload.sig',
      )
      expect(store.satelliteOrigin).toBe('https://sat.example.com')
    })

    it('scopes every call to the given deployment', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce(token)

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(mockApi.monitoring.getEligibility).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT)
      expect(mockApi.monitoring.mintLaunchToken).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT)
    })

    it('strips a trailing slash from the Satellite base URL', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce({
        ...token,
        satellite_base_url: 'https://sat.example.com/',
      })

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.launchUrl).toBe(
        'https://sat.example.com/monitoring/launch?token=header.payload.sig',
      )
    })

    it('URL-encodes the token', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce({ ...token, token: 'a b&c' })

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.launchUrl).toBe('https://sat.example.com/monitoring/launch?token=a%20b%26c')
    })
  })

  describe('unavailable', () => {
    it('is unavailable when minting the token fails', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockRejectedValueOnce(new Error('409'))

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('unavailable')
      expect(store.launchUrl).toBeNull()
    })

    it('is unavailable when the eligibility check fails', async () => {
      mockApi.monitoring.getEligibility.mockRejectedValueOnce(new Error('network'))

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('unavailable')
      expect(mockApi.monitoring.mintLaunchToken).not.toHaveBeenCalled()
    })
  })

  describe('session expiry', () => {
    it('markExpired moves an active session to expired', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
      mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce(token)
      await store.launch(ORG, ORBIT, DEPLOYMENT)

      store.markExpired()

      expect(store.status).toBe('expired')
    })

    it('markExpired is a no-op when not active', () => {
      store.markExpired()
      expect(store.status).toBe('idle')
    })

    it('re-launching after expiry mints a fresh token', async () => {
      mockApi.monitoring.getEligibility.mockResolvedValue(eligible)
      mockApi.monitoring.mintLaunchToken
        .mockResolvedValueOnce(token)
        .mockResolvedValueOnce({ ...token, token: 'fresh.token.sig' })
      await store.launch(ORG, ORBIT, DEPLOYMENT)
      store.markExpired()

      await store.launch(ORG, ORBIT, DEPLOYMENT)

      expect(store.status).toBe('active')
      expect(store.launchUrl).toContain('token=fresh.token.sig')
    })
  })

  it('reset clears all state', async () => {
    mockApi.monitoring.getEligibility.mockResolvedValueOnce(eligible)
    mockApi.monitoring.mintLaunchToken.mockResolvedValueOnce(token)
    await store.launch(ORG, ORBIT, DEPLOYMENT)

    store.reset()

    expect(store.status).toBe('idle')
    expect(store.launchToken).toBeNull()
    expect(store.reason).toBeNull()
    expect(store.launchUrl).toBeNull()
  })
})
