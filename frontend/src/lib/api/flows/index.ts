import type { AxiosInstance } from 'axios'
import type { Flow } from './interfaces'

export class FlowsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getList(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<Flow[]>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/flows`,
    )
    return responseData
  }

  async remove(organizationId: string, orbitId: string, flowId: string) {
    await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/flows/${flowId}`)
  }
}
