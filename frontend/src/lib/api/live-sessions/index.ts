import type { AxiosInstance } from 'axios'
import type { LiveSession, LiveSessionViewToken } from './interfaces'

export class LiveSessionsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getList(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<LiveSession[]>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/live-sessions`,
    )
    return responseData
  }

  async getItem(organizationId: string, orbitId: string, sessionId: string) {
    const { data: responseData } = await this.api.get<LiveSession>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/live-sessions/${sessionId}`,
    )
    return responseData
  }

  async issueViewToken(organizationId: string, orbitId: string, sessionId: string) {
    const { data: responseData } = await this.api.post<LiveSessionViewToken>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/live-sessions/${sessionId}/view-token`,
    )
    return responseData
  }

  async end(organizationId: string, orbitId: string, sessionId: string) {
    const { data: responseData } = await this.api.post<LiveSession>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/live-sessions/${sessionId}/end`,
    )
    return responseData
  }
}
