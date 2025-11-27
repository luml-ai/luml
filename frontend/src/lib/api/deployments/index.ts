import type { AxiosInstance } from 'axios'
import type { CreateDeploymentPayload, Deployment, UpdateDeploymentPayload } from './interfaces'

export class DeploymentsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async create(organizationId: string, orbitId: string, payload: CreateDeploymentPayload) {
    const { data: responseData } = await this.api.post<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments`,
      payload,
    )
    return responseData
  }

  async getList(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<Deployment[]>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments`,
    )
    return responseData
  }

  async getDeployment(organizationId: string, orbitId: string, deploymentId: string) {
    const { data: responseData } = await this.api.get<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
    )
    return responseData
  }

  async deleteDeployment(organizationId: string, orbitId: string, deploymentId: string) {
    const { data: responseData } = await this.api.delete<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
    )
    return responseData
  }

  async update(
    organizationId: string,
    orbitId: string,
    deploymentId: string,
    payload: UpdateDeploymentPayload,
  ) {
    const { data: responseData } = await this.api.patch<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
      payload,
    )
    return responseData
  }

  async forceDeleteDeployment(organizationId: string, orbitId: string, deploymentId: string) {
    const { data: responseData } = await this.api.delete(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}/force`,
    )
    return responseData
  }
}
