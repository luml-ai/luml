import type { HistorySnapshot, LineageCanvasNode } from '@/components/lineage/lineage.interface'
import type { LineageBatchIn, LineageNodeRef, LineagePair } from '@/lib/api/lineage/interfaces'
import type { Edge } from '@vue-flow/core'

function nodeReference(node: LineageCanvasNode): LineageNodeRef {
  if (node.data.nodeId) return { node_id: node.data.nodeId }
  if (node.data.artifactId) return { artifact_id: node.data.artifactId }
  throw new Error('Lineage node has no server node or artifact reference')
}

function referenceKey(reference: LineageNodeRef): string {
  return 'node_id' in reference ? `node:${reference.node_id}` : `artifact:${reference.artifact_id}`
}

function edgePair(edge: Edge, nodes: ReadonlyMap<string, LineageCanvasNode>): LineagePair {
  const source = nodes.get(edge.source)
  const target = nodes.get(edge.target)
  if (!source || !target) throw new Error('Lineage edge references a missing node')
  return { source: nodeReference(source), target: nodeReference(target) }
}

function pairKey(pair: LineagePair): string {
  return `${referenceKey(pair.source)}\u0000${referenceKey(pair.target)}`
}

export function buildLineageBatch(
  loaded: HistorySnapshot,
  current: HistorySnapshot,
): LineageBatchIn {
  const loadedNodes = new Map(loaded.nodes.map((node) => [node.id, node]))
  const currentNodes = new Map(current.nodes.map((node) => [node.id, node]))
  const loadedPairs = new Map(
    loaded.edges.map((edge) => [pairKey(edgePair(edge, loadedNodes)), edge]),
  )
  const currentPairs = new Map(
    current.edges.map((edge) => [
      pairKey(edgePair(edge, currentNodes)),
      edgePair(edge, currentNodes),
    ]),
  )

  // A node the server does not know yet only comes into being through a
  // connection: the position of an unconnected one (the focal node of an
  // empty graph) has nowhere to be stored.
  const connectedNodeIds = new Set(current.edges.flatMap((edge) => [edge.source, edge.target]))

  return {
    create: [...currentPairs].filter(([key]) => !loadedPairs.has(key)).map(([, pair]) => pair),
    delete: [...loadedPairs].filter(([key]) => !currentPairs.has(key)).map(([, edge]) => edge.id),
    positions: current.nodes
      .filter((node) => node.data.nodeId !== null || connectedNodeIds.has(node.id))
      .map((node) => ({
        ref: nodeReference(node),
        x: node.position.x,
        y: node.position.y,
      })),
  }
}

export function isEmptyLineageBatch(batch: LineageBatchIn): boolean {
  return batch.create.length === 0 && batch.delete.length === 0 && batch.positions.length === 0
}
