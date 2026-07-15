import type { AxiosInstance } from 'axios'
import type { MonitoringEligibility, MonitoringLaunchToken } from './interfaces'

export class MonitoringApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getEligibility(organizationId: string, orbitId: string, deploymentId: string) {
    const { data } = await this.api.get<MonitoringEligibility>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}/monitoring/eligibility`,
    )
    return data
  }

  async mintLaunchToken(organizationId: string, orbitId: string, deploymentId: string) {
    const { data } = await this.api.post<MonitoringLaunchToken>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}/monitoring/launch-token`,
    )
    return data
  }
}
