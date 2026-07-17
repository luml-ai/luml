import type { Artifact } from './../../lib/api/artifacts/interfaces'
import type { ArtifactTrack, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { Edge, Node } from '@vue-flow/core'

export type LineageNodeVariant = 'default' | 'main' | 'disabled'

export interface LinkCreatorForm {
  collection: string | null
  type: ArtifactTypeEnum | null
  artifactSearch: string | null
  artifact: string | null
}

export interface LineageNodeData {
  type: ArtifactTypeEnum
  title: string
  collectionName: string
  variant: LineageNodeVariant
  deployments?: Artifact['deployments']
  tracks?: ArtifactTrack[]
}

export interface HistorySnapshot {
  nodes: Node<Record<string, unknown>>[]
  edges: Edge[]
}
