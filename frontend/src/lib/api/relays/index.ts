import type { AxiosInstance } from 'axios'
import type { Relay, RelayCreatePayload, RelayUpdatePayload, RelayWithToken } from './interfaces'

export class RelaysApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getRelays(organizationId: string) {
    const { data } = await this.api.get<Relay[]>(`/v1/organizations/${organizationId}/relays`)
    return data
  }

  async createRelay(organizationId: string, payload: RelayCreatePayload) {
    const { data } = await this.api.post<RelayWithToken>(
      `/v1/organizations/${organizationId}/relays`,
      payload,
    )
    return data
  }

  async updateRelay(organizationId: string, relayId: string, payload: RelayUpdatePayload) {
    const { data } = await this.api.patch<Relay>(
      `/v1/organizations/${organizationId}/relays/${relayId}`,
      payload,
    )
    return data
  }

  async rotateRelayToken(organizationId: string, relayId: string) {
    const { data } = await this.api.post<RelayWithToken>(
      `/v1/organizations/${organizationId}/relays/${relayId}/rotate-token`,
    )
    return data
  }

  async deleteRelay(organizationId: string, relayId: string) {
    await this.api.delete(`/v1/organizations/${organizationId}/relays/${relayId}`)
  }
}
