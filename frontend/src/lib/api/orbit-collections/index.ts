import type { AxiosInstance } from 'axios'
import type { BaseDetailResponse } from '../api.interfaces'
import type {
  GetCollectionsListParams,
  GetCollectionsListResponse,
  OrbitCollectionCreator,
  ExtendedOrbitCollection,
} from './interfaces'
import qs from 'qs'

export class OrbitCollectionsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getCollectionsList(
    organizationId: string,
    orbitId: string,
    params: GetCollectionsListParams,
  ) {
    console.log('params', params)
    const { data: responseData } = await this.api.get<GetCollectionsListResponse>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/collections`,
      { params, paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }) },
    )
    return responseData
  }

  async createCollection(organizationId: string, orbitId: string, data: OrbitCollectionCreator) {
    const { data: responseData } = await this.api.post<ExtendedOrbitCollection>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/collections`,
      data,
    )
    return responseData
  }

  async updateCollection(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    data: Omit<OrbitCollectionCreator, 'type'>,
  ) {
    const { data: responseData } = await this.api.patch<ExtendedOrbitCollection>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`,
      data,
    )
    return responseData
  }

  async deleteCollection(organizationId: string, orbitId: string, collectionId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`,
    )
    return responseData
  }

  async getCollection(
    organizationId: string,
    orbitId: string,
    collectionId: string,
  ): Promise<ExtendedOrbitCollection> {
    const { data: responseData } = await this.api.get<ExtendedOrbitCollection>(
      `/api/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`,
    )
    return responseData
  }
}
