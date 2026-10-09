import type { LineageCanvasNode } from '@/components/lineage/lineage.interface'
import type { Edge, XYPosition } from '@vue-flow/core'

export const LEVEL_WIDTH = 320
export const ROW_HEIGHT = 120

function nextPositionInColumn(
  x: number,
  preferredY: number,
  positions: ReadonlyMap<string, XYPosition>,
): XYPosition {
  const column = [...positions.values()].filter((position) => position.x === x)
  if (column.length === 0) return { x, y: preferredY }
  return { x, y: Math.max(...column.map((position) => position.y)) + ROW_HEIGHT }
}

function adjacentPosition(
  nodeId: string,
  edge: Edge,
  neighbourPosition: XYPosition,
  positions: ReadonlyMap<string, XYPosition>,
): XYPosition {
  const x =
    edge.source === nodeId ? neighbourPosition.x - LEVEL_WIDTH : neighbourPosition.x + LEVEL_WIDTH
  return nextPositionInColumn(x, neighbourPosition.y, positions)
}

function layoutFromFocal(
  nodeIds: ReadonlySet<string>,
  edges: Edge[],
  focalNodeId: string,
): Map<string, XYPosition> {
  const positions = new Map<string, XYPosition>([[focalNodeId, { x: 0, y: 0 }]])
  const queue = [focalNodeId]

  for (let index = 0; index < queue.length; index += 1) {
    const currentId = queue[index]
    const currentPosition = positions.get(currentId)
    if (!currentPosition) continue

    for (const edge of edges) {
      let nextId: string | null = null
      if (edge.source === currentId) nextId = edge.target
      if (edge.target === currentId) nextId = edge.source
      if (!nextId || !nodeIds.has(nextId) || positions.has(nextId)) continue

      positions.set(nextId, adjacentPosition(nextId, edge, currentPosition, positions))
      queue.push(nextId)
    }
  }

  return positions
}

function layoutFromSavedPositions(
  nodes: LineageCanvasNode[],
  edges: Edge[],
  positionedNodeIds: ReadonlySet<string>,
): Map<string, XYPosition> {
  const positions = new Map<string, XYPosition>()
  for (const node of nodes) {
    if (positionedNodeIds.has(node.id)) positions.set(node.id, { ...node.position })
  }

  const pending = new Set(nodes.filter((node) => !positions.has(node.id)).map((node) => node.id))
  let madeProgress = true
  while (pending.size > 0 && madeProgress) {
    madeProgress = false
    for (const node of nodes) {
      if (!pending.has(node.id)) continue
      const edge = edges.find(
        (candidate) =>
          (candidate.source === node.id && positions.has(candidate.target)) ||
          (candidate.target === node.id && positions.has(candidate.source)),
      )
      if (!edge) continue

      const neighbourId = edge.source === node.id ? edge.target : edge.source
      const neighbourPosition = positions.get(neighbourId)
      if (!neighbourPosition) continue
      positions.set(node.id, adjacentPosition(node.id, edge, neighbourPosition, positions))
      pending.delete(node.id)
      madeProgress = true
    }
  }

  return positions
}

/**
 * First free slot in the column to the right of `anchor`: where a freshly
 * linked artifact appears so it lands next to the focal node, not at the origin.
 */
export function freePositionNear(anchor: XYPosition, taken: readonly XYPosition[]): XYPosition {
  const position = { x: anchor.x + LEVEL_WIDTH, y: anchor.y }
  const isTaken = (candidate: XYPosition): boolean =>
    taken.some(
      (existing) =>
        Math.abs(existing.x - candidate.x) < LEVEL_WIDTH * 0.75 &&
        Math.abs(existing.y - candidate.y) < ROW_HEIGHT * 0.75,
    )
  while (isTaken(position)) position.y += ROW_HEIGHT
  return position
}

function placeDisconnectedNodes(
  nodes: LineageCanvasNode[],
  positions: Map<string, XYPosition>,
): void {
  for (const node of nodes) {
    if (positions.has(node.id)) continue
    positions.set(node.id, nextPositionInColumn(0, 0, positions))
  }
}

export function layoutLineageNodes(
  nodes: LineageCanvasNode[],
  edges: Edge[],
  focalNodeId: string,
  positionedNodeIds: ReadonlySet<string> = new Set(),
): LineageCanvasNode[] {
  if (nodes.length === 0) return []

  const nodeIds = new Set(nodes.map((node) => node.id))
  const resolvedFocalId = nodeIds.has(focalNodeId) ? focalNodeId : nodes[0].id
  const positions =
    positionedNodeIds.size === 0
      ? layoutFromFocal(nodeIds, edges, resolvedFocalId)
      : layoutFromSavedPositions(nodes, edges, positionedNodeIds)

  placeDisconnectedNodes(nodes, positions)
  return nodes.map((node) => ({
    ...node,
    position: positions.get(node.id) ?? { x: 0, y: 0 },
  }))
}
