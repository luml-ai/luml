import type { Artifact, ArtifactTrack, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { Edge, Node } from '@vue-flow/core'

export type LineageNodeVariant = 'default' | 'main' | 'disabled'

export interface LinkCreatorForm {
  collection: string | null
  type: ArtifactTypeEnum | null
  artifactSearch: string | null
  artifact: string | null
}

export interface LineageNodeData {
  nodeId: string | null
  artifactId: string | null
  collectionId: string | null
  collectionName: string | null
  isDeleted: boolean
  type: ArtifactTypeEnum
  title: string
  variant: LineageNodeVariant
  data: Artifact | null
  deployments?: Artifact['deployments']
  tracks?: ArtifactTrack[]
}

export type LineageCanvasNode = Node<LineageNodeData> & { data: LineageNodeData }

export interface HistorySnapshot {
  nodes: LineageCanvasNode[]
  edges: Edge[]
}
