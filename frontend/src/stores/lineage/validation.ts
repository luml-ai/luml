import type { LineageCanvasNode } from '@/components/lineage/lineage.interface'
import type { Edge } from '@vue-flow/core'

export interface LineageConnection {
  source: string | null
  target: string | null
}

export function isValidLineageConnection(
  connection: LineageConnection,
  nodes: LineageCanvasNode[],
  edges: Edge[],
): boolean {
  const { source, target } = connection
  if (!source || !target || source === target) return false

  const sourceNode = nodes.find((node) => node.id === source)
  const targetNode = nodes.find((node) => node.id === target)
  if (!sourceNode || !targetNode || sourceNode.data.isDeleted || targetNode.data.isDeleted) {
    return false
  }

  return !edges.some(
    (edge) =>
      (edge.source === source && edge.target === target) ||
      (edge.source === target && edge.target === source),
  )
}

export function countUnconnectedArtifacts(nodes: LineageCanvasNode[], edges: Edge[]): number {
  const connectedNodeIds = new Set(edges.flatMap((edge) => [edge.source, edge.target]))
  return nodes.filter((node) => node.data.variant !== 'main' && !connectedNodeIds.has(node.id))
    .length
}
