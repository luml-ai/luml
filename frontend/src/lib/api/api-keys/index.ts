import type { AxiosInstance } from 'axios'
import type { CreateApiKeyResponse } from './interfaces'

export class ApiKeysApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async createApiKey() {
    const { data: responseData } = await this.api.post<CreateApiKeyResponse>(`/users/me/api-keys`)
    return responseData
  }

  async deleteApiKey() {
    await this.api.delete(`/users/me/api-keys`)
  }
}
