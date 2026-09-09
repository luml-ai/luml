import type { AxiosInstance } from 'axios'
import type {
  CreateArtifactResponse,
  GetArtifactsListParams,
  GetArtifactsListResponse,
  Artifact,
  ArtifactsDeleteConfirmRequest,
  ArtifactsDeleteRequest,
  ArtifactsDeleteResponse,
  ArtifactsDeleteUrlsResponse,
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
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`,
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
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`,
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
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`,
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
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/download-url`,
    )
    return responseData
  }

  async requestDeleteUrls(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactIds: string[],
  ): Promise<ArtifactsDeleteUrlsResponse> {
    const data: ArtifactsDeleteRequest = { artifact_ids: artifactIds }
    const { data: responseData } = await this.api.post<ArtifactsDeleteUrlsResponse>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/delete-urls`,
      data,
    )
    return responseData
  }

  async confirmDelete(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    artifactIds: string[],
    force = false,
  ): Promise<ArtifactsDeleteResponse> {
    const data: ArtifactsDeleteConfirmRequest = { artifact_ids: artifactIds, force }
    const { data: responseData } = await this.api.delete<ArtifactsDeleteResponse>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`,
      { data },
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
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/force`,
    )
  }

  async getById(organizationId: string, orbitId: string, collectionId: string, artifactId: string) {
    const { data: responseData } = await this.api.get<Artifact>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`,
    )
    return responseData
  }

  async getOrbitArtifacts(
    organizationId: string,
    orbitId: string,
    params: GetArtifactsListParams,
    signal: AbortSignal,
  ) {
    const { data: responseData } = await this.api.get<GetArtifactsListResponse>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts`,
      {
        params,
        signal,
        paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
      },
    )
    return responseData
  }
}
