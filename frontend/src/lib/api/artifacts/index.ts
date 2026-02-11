import type { AxiosInstance } from 'axios'
import type {
  CreateArtifactResponse,
  GetArtifactsListParams,
  GetArtifactsListResponse,
  Artifact,
  CreateArtifactPayload,
  UpdateArtifactPayload,
} from './interfaces'
import qs from 'qs'

export class ArtifactsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async create(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    data: CreateArtifactPayload,
  ) {
    const { data: responseData } = await this.api.post<CreateArtifactResponse>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`,
      data,
    )
    return responseData
  }

  async getList(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    params: GetArtifactsListParams,
    signal: AbortSignal,
  ) {
    const { data: responseData } = await this.api.get<GetArtifactsListResponse>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`,
      {
        params,
        signal,
        paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
      },
    )
    return responseData
  }

  async update(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactId: string,
    data: UpdateArtifactPayload,
  ) {
    const { data: responseData } = await this.api.patch<Artifact>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`,
      data,
    )
    return responseData
  }

  async getDownloadUrl(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactId: string,
  ) {
    const { data: responseData } = await this.api.get<{ url: string }>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/download-url`,
    )
    return responseData
  }

  async getDeleteUrl(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactId: string,
  ) {
    const { data: responseData } = await this.api.get<{ url: string }>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/delete-url`,
    )
    return responseData
  }

  async confirmDelete(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactId: string,
  ) {
    const { data: responseData } = await this.api.delete(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`,
    )
    return responseData
  }

  async forceDelete(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactId: string,
  ) {
    return this.api.delete(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/force`,
    )
  }

  async getById(organizationId: string, orbitId: string, collectionId: string, artifactId: string) {
    const { data: responseData } = await this.api.get<Artifact>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`,
    )
    return responseData
  }
}
