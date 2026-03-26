import type { AxiosInstance } from 'axios'
import type { OrbitSecret } from './interfaces'
import type { CreateSecretPayload, UpdateSecretPayload } from './interfaces'

export class OrbitSecretsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  public async getSecrets(organizationId: string, orbitId: string) {
    const { data } = await this.api.get<OrbitSecret[]>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/secrets`,
    )
    return data
  }

  public async getSecretById(organizationId: string, orbitId: string, secretId: string) {
    const { data } = await this.api.get<OrbitSecret>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`,
    )
    return data
  }

  public async createSecret(organizationId: string, orbitId: string, payload: CreateSecretPayload) {
    const { data } = await this.api.post<OrbitSecret>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/secrets`,
      payload,
    )
    return data
  }

  public async updateSecret(organizationId: string, orbitId: string, payload: UpdateSecretPayload) {
    const { data } = await this.api.patch<OrbitSecret>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${payload.id}`,
      payload,
    )
    return data
  }

  public async deleteSecret(organizationId: string, orbitId: string, secretId: string) {
    const { data } = await this.api.delete<{ detail: string }>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`,
    )
    return data
  }
}
