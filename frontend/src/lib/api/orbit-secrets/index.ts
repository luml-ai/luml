import type { AxiosInstance } from 'axios'
import type { OrbitSecret } from './interfaces'
import type { CreateSecretPayload, UpdateSecretPayload } from './interfaces'

export class OrbitSecretsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  public async getSecrets(organizationId: number, orbitId: number) {
    const { data } = await this.api.get<OrbitSecret[]>( `/organizations/${organizationId}/orbits/${orbitId}/secrets`, )
    return data
  }

  public async getSecretById(organizationId: number, orbitId: number, secretId: number) { 
	const { data } = await this.api.get<OrbitSecret>( `/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`,)
    return data
  }

  public async createSecret(organizationId: number, orbitId: number, payload: CreateSecretPayload) {
    const { data } = await this.api.post<OrbitSecret>( `/organizations/${organizationId}/orbits/${orbitId}/secrets`, payload, )
    return data
  }

  public async updateSecret(organizationId: number, orbitId: number, payload: UpdateSecretPayload) {
    const { data } = await this.api.patch<OrbitSecret>( `/organizations/${organizationId}/orbits/${orbitId}/secrets/${payload.id}`, payload, )
    return data
  }

  public async deleteSecret(organizationId: number, orbitId: number, secretId: number) {
    const { data } = await this.api.delete<{ detail: string }>(`/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`)
    return data
  }
}
