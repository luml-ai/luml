import type { AxiosInstance } from 'axios'
import type { BucketConnectionUrls, BucketSecret, BucketSecretCreator } from './interfaces'
import type { BaseDetailResponse } from '../DataforceApi.interfaces'

export class BucketSecretsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getBucketSecretsList(organizationId: number) {
    const { data: responseData } = await this.api.get<BucketSecret[]>(
      `/organizations/${organizationId}/bucket-secrets`,
    )
    return responseData
  }

  async getBucketSecret(organizationId: number, secretId: number) {
    const { data: responseData } = await this.api.get<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}`,
    )
    return responseData
  }

  async createBucketSecret(organizationId: number, data: BucketSecretCreator) {
    const { data: responseData } = await this.api.post<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets`,
      data,
    )
    return responseData
  }

  async updateBucketSecret(
    organizationId: number,
    secretId: number,
    data: BucketSecretCreator & { id: number },
  ) {
    const { data: responseData } = await this.api.patch<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}`,
      data,
    )
    return responseData
  }

  async deleteBucketSecret(organizationId: number, secretId: number) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}`,
    )
    return responseData
  }

  async getBucketSecretConnectionUrls(data: BucketSecretCreator) {
    const { data: responseData } = await this.api.post<BucketConnectionUrls>(
      `bucket-secrets/urls`,
      data,
    )
    return responseData
  }
}
