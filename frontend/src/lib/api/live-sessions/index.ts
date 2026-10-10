import type { AxiosInstance } from 'axios'
import type { LiveSessionViewToken } from './interfaces'

export class LiveSessionsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async issueViewToken(organizationId: string, orbitId: string, sessionId: string) {
    const { data: responseData } = await this.api.post<LiveSessionViewToken>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/live-sessions/${sessionId}/view-token`,
    )
    return responseData
  }
}
