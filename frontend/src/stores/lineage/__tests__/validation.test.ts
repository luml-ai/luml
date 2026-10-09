import type { Edge } from '@vue-flow/core'
import { describe, expect, it } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { LineageCanvasNode, LineageNodeData } from '@/components/lineage/lineage.interface'
import { countUnconnectedArtifacts, isValidLineageConnection } from '../validation'

function node(
  id: string,
  variant: LineageNodeData['variant'] = 'default',
  isDeleted = false,
): LineageCanvasNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      nodeId: id,
      artifactId: isDeleted ? null : id,
      collectionId: isDeleted ? null : 'collection',
      collectionName: 'Collection',
      isDeleted,
      type: ArtifactTypeEnum.model,
      title: id,
      variant,
      data: null,
    },
  }
}

describe('isValidLineageConnection', () => {
  const nodes = [node('A'), node('B'), node('N', 'disabled', true)]
  const edges: Edge[] = [{ id: 'a-b', source: 'A', target: 'B' }]

  it.each([
    ['a loop', { source: 'A', target: 'A' }],
    ['a duplicate', { source: 'A', target: 'B' }],
    ['a reverse pair', { source: 'B', target: 'A' }],
    ['a connection to a deleted target', { source: 'A', target: 'N' }],
    ['a connection from a deleted source', { source: 'N', target: 'A' }],
  ])('rejects %s', (_, connection) => {
    expect(isValidLineageConnection(connection, nodes, edges)).toBe(false)
  })

  it('accepts a new pair between live nodes', () => {
    expect(
      isValidLineageConnection({ source: 'B', target: 'C' }, [...nodes, node('C')], edges),
    ).toBe(true)
  })
})

describe('countUnconnectedArtifacts', () => {
  it('excludes the focal node and counts other nodes without an edge', () => {
    const nodes = [node('M', 'main'), node('A'), node('B')]
    expect(countUnconnectedArtifacts(nodes, [{ id: 'a-m', source: 'A', target: 'M' }])).toBe(1)
    expect(
      countUnconnectedArtifacts(nodes, [
        { id: 'a-m', source: 'A', target: 'M' },
        { id: 'm-b', source: 'M', target: 'B' },
      ]),
    ).toBe(0)
  })
})
