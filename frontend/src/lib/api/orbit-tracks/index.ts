import type { AxiosInstance } from 'axios'
import type {
  ITrack,
  ITracksList,
  ITrackCreate,
  ITrackUpdate,
  ITrackArtifact,
  ITrackArtifactCreate,
  ITrackArtifactUpdate,
  ITrackArtifactUpdateResponse,
  ITrackEntriesList,
  ITrackStage,
  ITrackStageCreate,
  ITrackStageUpdate,
  ITrackStagesList,
  GetTrackEntriesListParams,
} from './interfaces'

export class OrbitTracksApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  // --- Tracks ---

  async createTrack(organizationId: string, orbitId: string, data: ITrackCreate): Promise<ITrack> {
    const { data: responseData } = await this.api.post<ITrack>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks`,
      data,
    )
    return responseData
  }

  async listTracks(organizationId: string, orbitId: string): Promise<ITracksList> {
    const { data: responseData } = await this.api.get<ITracksList>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks`,
    )
    return responseData
  }

  async getTrack(organizationId: string, orbitId: string, trackId: string): Promise<ITrack> {
    const { data: responseData } = await this.api.get<ITrack>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`,
    )
    return responseData
  }

  async updateTrack(
    organizationId: string,
    orbitId: string,
    trackId: string,
    data: ITrackUpdate,
  ): Promise<ITrack> {
    const { data: responseData } = await this.api.patch<ITrack>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`,
      data,
    )
    return responseData
  }

  async deleteTrack(organizationId: string, orbitId: string, trackId: string): Promise<void> {
    await this.api.delete(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`,
    )
  }

  // --- Entries ---

  async addEntry(
    organizationId: string,
    orbitId: string,
    trackId: string,
    data: ITrackArtifactCreate,
  ): Promise<ITrackArtifact> {
    const { data: responseData } = await this.api.post<ITrackArtifact>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries`,
      data,
    )
    return responseData
  }

  async listEntries(
    organizationId: string,
    orbitId: string,
    trackId: string,
    params?: GetTrackEntriesListParams,
  ): Promise<ITrackEntriesList> {
    const { data: responseData } = await this.api.get<ITrackEntriesList>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries`,
      { params },
    )
    return responseData
  }

  async patchEntry(
    organizationId: string,
    orbitId: string,
    trackId: string,
    entryId: string,
    data: ITrackArtifactUpdate,
    force?: boolean,
  ): Promise<ITrackArtifactUpdateResponse> {
    const { data: responseData } = await this.api.patch<ITrackArtifactUpdateResponse>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries/${entryId}`,
      data,
      { params: force ? { force: true } : undefined },
    )
    return responseData
  }

  async deleteEntry(
    organizationId: string,
    orbitId: string,
    trackId: string,
    entryId: string,
  ): Promise<void> {
    await this.api.delete(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries/${entryId}`,
    )
  }

  // --- Artifact track membership ---

  async listArtifactEntries(
    organizationId: string,
    orbitId: string,
    artifactId: string,
  ): Promise<ITrackEntriesList> {
    const { data: responseData } = await this.api.get<ITrackEntriesList>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts/${artifactId}/track-entries`,
    )
    return responseData
  }

  // --- Stages ---

  async createStage(
    organizationId: string,
    orbitId: string,
    trackId: string,
    data: ITrackStageCreate,
  ): Promise<ITrackStage> {
    const { data: responseData } = await this.api.post<ITrackStage>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages`,
      data,
    )
    return responseData
  }

  async listStages(
    organizationId: string,
    orbitId: string,
    trackId: string,
  ): Promise<ITrackStagesList> {
    const { data: responseData } = await this.api.get<ITrackStagesList>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages`,
    )
    return responseData
  }

  async updateStage(
    organizationId: string,
    orbitId: string,
    trackId: string,
    stageId: string,
    data: ITrackStageUpdate,
  ): Promise<ITrackStage> {
    const { data: responseData } = await this.api.patch<ITrackStage>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages/${stageId}`,
      data,
    )
    return responseData
  }

  async deleteStage(
    organizationId: string,
    orbitId: string,
    trackId: string,
    stageId: string,
    force?: boolean,
  ): Promise<void> {
    await this.api.delete(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages/${stageId}`,
      { params: force ? { force: true } : undefined },
    )
  }
}
