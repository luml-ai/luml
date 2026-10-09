import type { Edge } from '@vue-flow/core'
import { describe, expect, it } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { LineageCanvasNode, LineageNodeData } from '@/components/lineage/lineage.interface'
import { LEVEL_WIDTH, ROW_HEIGHT, freePositionNear, layoutLineageNodes } from '../layout'

function node(id: string, x = 0, y = 0): LineageCanvasNode {
  const data: LineageNodeData = {
    nodeId: id,
    artifactId: id,
    collectionId: 'collection',
    collectionName: 'Collection',
    isDeleted: false,
    type: ArtifactTypeEnum.model,
    title: id,
    variant: id === 'M' ? 'main' : 'default',
    data: null,
  }
  return { id, type: 'lineage', position: { x, y }, data }
}

function positions(nodes: LineageCanvasNode[]) {
  return Object.fromEntries(nodes.map((item) => [item.id, item.position]))
}

describe('layoutLineageNodes', () => {
  it('places a full directed graph in breadth-first columns around the focal node', () => {
    const nodes = ['M', 'A', 'B', 'C', 'Z'].map((id) => node(id))
    const edges: Edge[] = [
      { id: 'a-m', source: 'A', target: 'M' },
      { id: 'b-m', source: 'B', target: 'M' },
      { id: 'm-c', source: 'M', target: 'C' },
      { id: 'z-a', source: 'Z', target: 'A' },
    ]

    expect(positions(layoutLineageNodes(nodes, edges, 'M'))).toEqual({
      M: { x: 0, y: 0 },
      A: { x: -LEVEL_WIDTH, y: 0 },
      B: { x: -LEVEL_WIDTH, y: ROW_HEIGHT },
      C: { x: LEVEL_WIDTH, y: 0 },
      Z: { x: -2 * LEVEL_WIDTH, y: 0 },
    })
  })

  it('keeps saved coordinates and places missing nodes below occupied neighbour columns', () => {
    const nodes = [node('M', 15, 25), node('D', -305, 25), node('E'), node('X', 335, 25)]
    const edges: Edge[] = [
      { id: 'd-m', source: 'D', target: 'M' },
      { id: 'e-m', source: 'E', target: 'M' },
      { id: 'm-x', source: 'M', target: 'X' },
    ]
    const positioned = new Set(['M', 'D', 'X'])

    expect(positions(layoutLineageNodes(nodes, edges, 'M', positioned))).toEqual({
      M: { x: 15, y: 25 },
      D: { x: -305, y: 25 },
      E: { x: -305, y: 145 },
      X: { x: 335, y: 25 },
    })
  })

  it('keeps the first position found when cycles reach a node more than once', () => {
    const nodes = ['A', 'B', 'C'].map((id) => node(id))
    const edges: Edge[] = [
      { id: 'a-b', source: 'A', target: 'B' },
      { id: 'b-c', source: 'B', target: 'C' },
      { id: 'c-a', source: 'C', target: 'A' },
    ]

    expect(positions(layoutLineageNodes(nodes, edges, 'A'))).toEqual({
      A: { x: 0, y: 0 },
      B: { x: LEVEL_WIDTH, y: 0 },
      C: { x: -LEVEL_WIDTH, y: 0 },
    })
  })
})

describe('freePositionNear', () => {
  it('takes the column right of the anchor and skips occupied rows', () => {
    const anchor = { x: 100, y: 50 }

    expect(freePositionNear(anchor, [anchor])).toEqual({ x: 100 + LEVEL_WIDTH, y: 50 })
    expect(freePositionNear(anchor, [anchor, { x: 100 + LEVEL_WIDTH, y: 50 }])).toEqual({
      x: 100 + LEVEL_WIDTH,
      y: 50 + ROW_HEIGHT,
    })
    // A node half a row away still blocks the slot.
    expect(
      freePositionNear(anchor, [anchor, { x: 100 + LEVEL_WIDTH, y: 50 + ROW_HEIGHT / 2 }]),
    ).toEqual({ x: 100 + LEVEL_WIDTH, y: 50 + 2 * ROW_HEIGHT })
  })
})
