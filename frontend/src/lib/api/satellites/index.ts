import type { AxiosInstance } from 'axios'
import type {
  CreateSatellitePayload,
  CreateSatelliteResponse,
  RegenerateApiKeyResponse,
  Satellite,
} from './interfaces'

export class SatellitesApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async create(organizationId: string, orbitId: string, payload: CreateSatellitePayload) {
    const { data: responseData } = await this.api.post<CreateSatelliteResponse>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites`,
      payload,
    )
    return responseData
  }

  async update(
    organizationId: string,
    orbitId: string,
    satelliteId: string,
    payload: CreateSatellitePayload,
  ) {
    const { data: responseData } = await this.api.patch<Satellite>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`,
      payload,
    )
    return responseData
  }

  async getList(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<Satellite[]>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites`,
    )
    return responseData
  }

  async getItem(organizationId: string, orbitId: string, satelliteId: string) {
    const { data: responseData } = await this.api.get<Satellite>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`,
    )
    return responseData
  }

  async delete(organizationId: string, orbitId: string, satelliteId: string) {
    const { data: responseData } = await this.api.delete(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`,
    )
    return responseData
  }

  async regenerateApiKye(organizationId: string, orbitId: string, satelliteId: string) {
    const { data: responseData } = await this.api.post<RegenerateApiKeyResponse>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}/api-key`,
    )
    return responseData
  }
}
