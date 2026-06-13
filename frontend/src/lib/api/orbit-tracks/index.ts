import type { AxiosInstance } from 'axios'
import type { BaseDetailResponse } from '../api.interfaces'
import type {
  GetTrackEntriesListParams,
  GetTracksListParams,
  Track,
  TrackCreateIn,
  TrackEntriesList,
  TrackEntry,
  TrackEntryCreateIn,
  TrackEntryUpdateIn,
  TracksList,
  TrackStage,
  TrackStageCreateIn,
  TrackStageUpdateIn,
  TrackUpdateIn,
} from './interfaces'
import qs from 'qs'

export class OrbitTracksApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  private basePath(organizationId: string, orbitId: string) {
    return `/v1/organizations/${organizationId}/orbits/${orbitId}/tracks`
  }

  // --- Tracks ---

  async createTrack(organizationId: string, orbitId: string, data: TrackCreateIn) {
    const { data: responseData } = await this.api.post<Track>(
      this.basePath(organizationId, orbitId),
      data,
    )
    return responseData
  }

  async listTracks(organizationId: string, orbitId: string, params: GetTracksListParams) {
    const { data: responseData } = await this.api.get<TracksList>(
      this.basePath(organizationId, orbitId),
      { params, paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }) },
    )
    return responseData
  }

  async getTrack(organizationId: string, orbitId: string, trackId: string) {
    const { data: responseData } = await this.api.get<Track>(
      `${this.basePath(organizationId, orbitId)}/${trackId}`,
    )
    return responseData
  }

  async updateTrack(organizationId: string, orbitId: string, trackId: string, data: TrackUpdateIn) {
    const { data: responseData } = await this.api.patch<Track>(
      `${this.basePath(organizationId, orbitId)}/${trackId}`,
      data,
    )
    return responseData
  }

  async deleteTrack(organizationId: string, orbitId: string, trackId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `${this.basePath(organizationId, orbitId)}/${trackId}`,
    )
    return responseData
  }

  // --- Entries ---

  async addEntry(
    organizationId: string,
    orbitId: string,
    trackId: string,
    data: TrackEntryCreateIn,
  ) {
    const { data: responseData } = await this.api.post<TrackEntry>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries`,
      data,
    )
    return responseData
  }

  async listEntries(
    organizationId: string,
    orbitId: string,
    trackId: string,
    params: GetTrackEntriesListParams,
  ) {
    const { data: responseData } = await this.api.get<TrackEntriesList>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries`,
      { params },
    )
    return responseData
  }

  async patchEntry(
    organizationId: string,
    orbitId: string,
    trackId: string,
    entryId: string,
    data: TrackEntryUpdateIn,
    force?: boolean,
  ) {
    const { data: responseData } = await this.api.patch<TrackEntry>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries/${entryId}`,
      data,
      { params: force ? { force: true } : undefined },
    )
    return responseData
  }

  async deleteEntry(organizationId: string, orbitId: string, trackId: string, entryId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries/${entryId}`,
    )
    return responseData
  }

  async deleteEntries(
    organizationId: string,
    orbitId: string,
    trackId: string,
    entryIds: string[],
  ) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries`,
      { params: { entry_ids: entryIds } },
    )
    return responseData
  }

  // --- Stages ---

  async createStage(
    organizationId: string,
    orbitId: string,
    trackId: string,
    data: TrackStageCreateIn,
  ) {
    const { data: responseData } = await this.api.post<TrackStage>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/stages`,
      data,
    )
    return responseData
  }

  async listStages(organizationId: string, orbitId: string, trackId: string) {
    const { data: responseData } = await this.api.get<TrackStage[]>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/stages`,
    )
    return responseData
  }

  async updateStage(
    organizationId: string,
    orbitId: string,
    trackId: string,
    stageId: string,
    data: TrackStageUpdateIn,
  ) {
    const { data: responseData } = await this.api.patch<TrackStage>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/stages/${stageId}`,
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
  ) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/stages/${stageId}`,
      { params: force ? { force: true } : undefined },
    )
    return responseData
  }

  async getEntryByStage(organizationId: string, orbitId: string, trackId: string, stageId: string) {
    const { data: responseData } = await this.api.get<TrackEntry>(
      `${this.basePath(organizationId, orbitId)}/${trackId}/entries/by-stage`,
      { params: { stage_id: stageId } },
    )
    return responseData
  }
}
