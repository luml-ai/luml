import type { ArtifactTypeEnum } from '../artifacts/interfaces'

export interface Track {
  id: string
  orbit_id: string
  name: string
  artifact_type: ArtifactTypeEnum
  description: string | null
  tags: string[] | null
  created_by: string
  next_version: number
  total_entries: number
  created_at: string
  updated_at: string | null
}

export interface TrackCreateIn {
  name: string
  artifact_type: ArtifactTypeEnum
  description?: string | null
  tags?: string[] | null
}

export interface TrackUpdateIn {
  name?: string | null
  description?: string | null
  tags?: string[] | null
}

export interface TrackStage {
  id: string
  track_id: string
  name: string
  created_at: string
  updated_at: string | null
}

export interface TrackStageCreateIn {
  name: string
}

export interface TrackStageUpdateIn {
  name?: string | null
}

export interface TrackEntry {
  id: string
  track_id: string
  artifact_id: string
  version: number
  stage_id: string | null
  added_by: string
  created_at: string
  updated_at: string | null
  artifact_name: string | null
  artifact_description: string | null
  stage_name: string | null
}

export interface TrackEntryCreateIn {
  artifact_id: string
}

export interface TrackEntryUpdateIn {
  stage_id?: string | null
}

export interface TrackEntriesList {
  items: TrackEntry[]
  cursor: string | null
}

export interface TracksList {
  items: Track[]
  cursor: string | null
}

export interface GetTracksListParams {
  cursor: string | null
  limit?: number
  sort_by?: 'created_at' | 'name' | 'artifact_type' | 'description' | 'total_entries'
  order?: 'asc' | 'desc'
  search?: string
  types?: ArtifactTypeEnum[]
}

export interface GetTrackEntriesListParams {
  cursor: string | null
  limit?: number
  order?: 'asc' | 'desc'
  stage?: string
}
