import type { AxiosInstance } from 'axios'
import type {
  BucketConnectionUrls,
  BucketSecret,
  BucketSecretCreator,
  BucketSecretValidator,
} from './interfaces'
import type { BaseDetailResponse } from '../api.interfaces'

export class BucketSecretsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getBucketSecretsList(organizationId: string) {
    const { data: responseData } = await this.api.get<BucketSecret[]>(
      `/organizations/${organizationId}/bucket-secrets`,
    )
    return responseData
  }

  async getBucketSecret(organizationId: string, secretId: string) {
    const { data: responseData } = await this.api.get<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}`,
    )
    return responseData
  }

  async createBucketSecret(organizationId: string, data: BucketSecretCreator) {
    const { data: responseData } = await this.api.post<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets`,
      data,
    )
    return responseData
  }

  async updateBucketSecret(
    organizationId: string,
    secretId: string,
    data: BucketSecretCreator & { id: string },
  ) {
    const { data: responseData } = await this.api.patch<BucketSecret>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}`,
      data,
    )
    return responseData
  }

  async deleteBucketSecret(organizationId: string, secretId: string) {
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

  async getExistingBucketSecretConnectionUrls(
    organizationId: string,
    secretId: string,
    data: BucketSecretValidator,
  ) {
    const { data: responseData } = await this.api.post<BucketConnectionUrls>(
      `/organizations/${organizationId}/bucket-secrets/${secretId}/urls`,
      data,
    )
    return responseData
  }
}
