export interface ITrackCreate {
  name: string
  artifact_type: string
  description?: string | null
  tags?: string[]
}

export interface ITrack {
  id: string
  orbit_id: string
  name: string
  artifact_type: string
  description: string | null
  tags: string[] | null
  created_by: string
  created_at: string
  updated_at: string | null
  total_entries: number
}

export interface ITrackUpdate {
  name?: string | null
  description?: string | null
  tags?: string[] | null
}

export interface ITracksList {
  items: ITrack[]
  cursor: string | null
}

export interface ITrackArtifactCreate {
  artifact_id: string
}

export interface ITrackArtifactStage {
  id: string
  name: string
}

export interface ITrackArtifact {
  id: string
  track_id: string
  artifact_id: string
  version: number
  stage: ITrackArtifactStage | null
  created_at: string
  added_by: string
}

export interface ITrackArtifactUpdate {
  stage_id: string | null
}

export interface ITrackArtifactUpdateResponse {
  entry: ITrackArtifact
}

export interface ITrackEntriesList {
  items: ITrackArtifact[]
  cursor: string | null
}

export interface ITrackStageConflict {
  stage_name: string
  held_by_version: number
}

export interface ITrackStageCreate {
  name: string
}

export interface ITrackStage {
  id: string
  track_id: string
  name: string
  created_at: string
}

export interface ITrackStageUpdate {
  name?: string | null
}

export interface ITrackStagesList {
  items: ITrackStage[]
  cursor: string | null
}

export interface GetTrackEntriesListParams {
  stage?: string
  cursor?: string | null
  page_size?: number
}
