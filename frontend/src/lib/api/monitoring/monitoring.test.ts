import { describe, it, expect, vi } from 'vitest'
import type { AxiosInstance } from 'axios'
import { MonitoringApi } from './index'

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const DEPLOYMENT = 'deployment-a'

function makeApi(response: unknown) {
  const get = vi.fn().mockResolvedValue({ data: response })
  const post = vi.fn().mockResolvedValue({ data: response })
  const instance = { get, post } as unknown as AxiosInstance
  return { instance, get, post }
}

describe('MonitoringApi', () => {
  it('reads eligibility from the deployment-scoped endpoint', async () => {
    const eligibility = { eligible: true, satellite_base_url: 'https://s', reason: null }
    const { instance, get } = makeApi(eligibility)

    const result = await new MonitoringApi(instance).getEligibility(ORG, ORBIT, DEPLOYMENT)

    expect(get).toHaveBeenCalledWith(
      `/v1/organizations/${ORG}/orbits/${ORBIT}/deployments/${DEPLOYMENT}/monitoring/eligibility`,
    )
    expect(result).toEqual(eligibility)
  })

  it('mints the launch token via POST on the deployment-scoped endpoint', async () => {
    const tokenResponse = {
      token: 't',
      satellite_base_url: 'https://s',
      expires_at: 1_800_000_000,
    }
    const { instance, post } = makeApi(tokenResponse)

    const result = await new MonitoringApi(instance).mintLaunchToken(ORG, ORBIT, DEPLOYMENT)

    expect(post).toHaveBeenCalledWith(
      `/v1/organizations/${ORG}/orbits/${ORBIT}/deployments/${DEPLOYMENT}/monitoring/launch-token`,
    )
    expect(result).toEqual(tokenResponse)
  })
})
