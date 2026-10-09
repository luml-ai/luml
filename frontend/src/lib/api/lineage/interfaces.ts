import type { Artifact, ArtifactTypeEnum } from '../artifacts/interfaces'

export type LineageVia = 'ui' | 'api'

export interface LineageEdge {
  id: string
  source: string
  target: string
  created_by_user: string
  created_via: LineageVia
  created_at: string
}

export interface LineageNode {
  id: string
  artifact_id: string | null
  type: ArtifactTypeEnum
  name: string
  collection_name: string | null
  x: number | null
  y: number | null
  is_deleted: boolean
  data: Artifact | null
}

export interface LineageGraph {
  nodes: LineageNode[]
  edges: LineageEdge[]
  focal_artifact_id: string
  depth: number | null
  truncated: boolean
}

export type LineageNodeRef =
  | { artifact_id: string; node_id?: never }
  | { artifact_id?: never; node_id: string }

export interface LineagePosition {
  ref: LineageNodeRef
  x: number
  y: number
}

export interface LineagePair {
  source: LineageNodeRef
  target: LineageNodeRef
}

export interface LineageBatchIn {
  create: LineagePair[]
  delete: string[]
  positions: LineagePosition[]
}

export interface LineageBatchResult {
  created: LineageEdge[]
  deleted: LineageEdge[]
}

export interface LineageCreateIn {
  target_artifact_ids: string[]
}
