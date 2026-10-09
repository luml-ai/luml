import type {
  HistorySnapshot,
  LineageCanvasNode,
  LineageNodeData,
} from '@/components/lineage/lineage.interface'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import type { LineageGraph, LineageNode } from '@/lib/api/lineage/interfaces'
import type { Edge } from '@vue-flow/core'
import { layoutLineageNodes } from './layout'

export interface LineageFocalArtifact extends Artifact {
  collection: {
    id: string
    name: string
  }
}

export function artifactCanvasNodeId(artifactId: string): string {
  return `artifact:${artifactId}`
}

export function artifactNodeData(
  artifact: Artifact,
  collection: { id: string; name: string },
  variant: LineageNodeData['variant'] = 'default',
): LineageNodeData {
  return {
    nodeId: null,
    artifactId: artifact.id,
    collectionId: collection.id,
    collectionName: collection.name,
    isDeleted: false,
    type: artifact.type,
    title: artifact.name,
    variant,
    data: artifact,
    deployments: artifact.deployments,
    tracks: artifact.tracks,
  }
}

function synthesizeFocalNode(artifact: LineageFocalArtifact): LineageCanvasNode {
  return {
    id: artifactCanvasNodeId(artifact.id),
    type: 'lineage',
    position: { x: 0, y: 0 },
    data: artifactNodeData(artifact, artifact.collection, 'main'),
  }
}

function mapNode(node: LineageNode, focalArtifactId: string): LineageCanvasNode {
  const variant: LineageNodeData['variant'] = node.is_deleted
    ? 'disabled'
    : node.artifact_id === focalArtifactId
      ? 'main'
      : 'default'
  return {
    id: node.id,
    type: 'lineage',
    position: { x: node.x ?? 0, y: node.y ?? 0 },
    connectable: !node.is_deleted,
    data: {
      nodeId: node.id,
      artifactId: node.artifact_id,
      collectionId: node.data?.collection_id ?? null,
      collectionName: node.collection_name,
      isDeleted: node.is_deleted,
      type: node.type,
      title: node.name,
      variant,
      data: node.data,
      deployments: node.data?.deployments ?? [],
      tracks: node.data?.tracks ?? [],
    },
  }
}

function mapEdge(edge: LineageGraph['edges'][number]): Edge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'custom',
  }
}

export function mapGraphToCanvas(
  graph: LineageGraph,
  currentArtifact: LineageFocalArtifact,
): HistorySnapshot {
  if (graph.nodes.length === 0) {
    return { nodes: [synthesizeFocalNode(currentArtifact)], edges: [] }
  }

  const nodes = graph.nodes.map((node) => mapNode(node, graph.focal_artifact_id))
  const edges = graph.edges.map(mapEdge)
  let focalNode = nodes.find((node) => node.data.artifactId === graph.focal_artifact_id)
  if (!focalNode) {
    focalNode = synthesizeFocalNode(currentArtifact)
    nodes.push(focalNode)
  }
  const positionedNodeIds = new Set(
    graph.nodes.filter((node) => node.x !== null && node.y !== null).map((node) => node.id),
  )
  if (focalNode.id.startsWith('artifact:')) positionedNodeIds.add(focalNode.id)

  return {
    nodes: layoutLineageNodes(nodes, edges, focalNode.id, positionedNodeIds),
    edges,
  }
}
