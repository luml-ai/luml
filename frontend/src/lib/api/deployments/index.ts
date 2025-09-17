import type { AxiosInstance } from 'axios'
import type { CreateDeploymentPayload, Deployment, UpdateDeploymentPayload } from './interfaces'

export class DeploymentsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async create(organizationId: number, orbitId: number, payload: CreateDeploymentPayload) {
    const { data: responseData } = await this.api.post<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments`,
      payload,
    )
    return responseData
  }

  async getList(organizationId: number, orbitId: number) {
    const { data: responseData } = await this.api.get<Deployment[]>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments`,
    )
    return responseData
  }

  async getDeployment(organizationId: number, orbitId: number, deploymentId: number) {
    const { data: responseData } = await this.api.get<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
    )
    return responseData
  }

  async deleteDeployment(organizationId: number, orbitId: number, deploymentId: number) {
    const { data: responseData } = await this.api.delete<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
    )
    return responseData
  }

  async update(
    organizationId: number,
    orbitId: number,
    deploymentId: number,
    payload: UpdateDeploymentPayload,
  ) {
    const { data: responseData } = await this.api.patch<Deployment>(
      `/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`,
      payload,
    )
    return responseData
  }
}
