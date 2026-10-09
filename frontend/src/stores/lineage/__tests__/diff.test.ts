import type { Edge } from '@vue-flow/core'
import { describe, expect, it } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type {
  HistorySnapshot,
  LineageCanvasNode,
  LineageNodeData,
} from '@/components/lineage/lineage.interface'
import { buildLineageBatch, isEmptyLineageBatch } from '../diff'

function node(
  id: string,
  nodeId: string | null,
  artifactId: string | null,
  x: number,
  y: number,
  variant: LineageNodeData['variant'] = 'default',
): LineageCanvasNode {
  return {
    id,
    type: 'lineage',
    position: { x, y },
    data: {
      nodeId,
      artifactId,
      collectionId: artifactId ? `collection-${artifactId}` : null,
      collectionName: 'Collection',
      isDeleted: artifactId === null,
      type: ArtifactTypeEnum.model,
      title: artifactId ?? 'Deleted',
      variant,
      data: null,
    },
  }
}

function state(nodes: LineageCanvasNode[], edges: Edge[]): HistorySnapshot {
  return { nodes, edges }
}

describe('buildLineageBatch', () => {
  it('creates a connection by artifact reference and includes every node position', () => {
    const model = node('artifact:model', null, 'model', 0, 0, 'main')
    const dataset = node('artifact:dataset', null, 'dataset', -260, 0)
    const loaded = state([model], [])
    const current = state(
      [model, dataset],
      [{ id: 'draft-edge', source: 'artifact:dataset', target: 'artifact:model' }],
    )

    expect(buildLineageBatch(loaded, current)).toEqual({
      create: [
        {
          source: { artifact_id: 'dataset' },
          target: { artifact_id: 'model' },
        },
      ],
      delete: [],
      positions: [
        { ref: { artifact_id: 'model' }, x: 0, y: 0 },
        { ref: { artifact_id: 'dataset' }, x: -260, y: 0 },
      ],
    })
  })

  it('expresses unlink and replace as deletions plus a new artifact pair at the old position', () => {
    const model = node('node-model', 'node-model', 'model', 0, 0, 'main')
    const dataset = node('node-dataset', 'node-dataset', 'dataset', -320, 0)
    const output = node('node-output', 'node-output', 'output', 320, 0)
    const loaded = state(
      [model, dataset, output],
      [
        { id: 'edge-dataset', source: 'node-dataset', target: 'node-model' },
        { id: 'edge-output', source: 'node-model', target: 'node-output' },
      ],
    )
    const replacement = node('artifact:dataset-new', null, 'dataset-new', -320, 0)
    const current = state(
      [model, replacement],
      [{ id: 'edge-dataset', source: 'artifact:dataset-new', target: 'node-model' }],
    )

    expect(buildLineageBatch(loaded, current)).toEqual({
      create: [
        {
          source: { artifact_id: 'dataset-new' },
          target: { node_id: 'node-model' },
        },
      ],
      delete: ['edge-dataset', 'edge-output'],
      positions: [
        { ref: { node_id: 'node-model' }, x: 0, y: 0 },
        { ref: { artifact_id: 'dataset-new' }, x: -320, y: 0 },
      ],
    })
  })

  it('leaves out the position of an unconnected node the server does not know', () => {
    // The focal node of an empty graph exists only on the canvas: there is
    // no lineage node to store its position on.
    const focal = node('artifact:model', null, 'model', 0, 0, 'main')
    const loaded = state([focal], [])

    const moved = buildLineageBatch(loaded, state([{ ...focal, position: { x: 40, y: 10 } }], []))
    expect(moved).toEqual({ create: [], delete: [], positions: [] })
    expect(isEmptyLineageBatch(moved)).toBe(true)

    const known = node('node-model', 'node-model', 'model', 0, 0, 'main')
    const kept = buildLineageBatch(
      state([known], []),
      state([{ ...known, position: { x: 40, y: 10 } }], []),
    )
    expect(kept.positions).toEqual([{ ref: { node_id: 'node-model' }, x: 40, y: 10 }])
    expect(isEmptyLineageBatch(kept)).toBe(false)
  })

  it('sends all positions after a move without recreating existing connections', () => {
    const a = node('node-a', 'node-a', 'a', 0, 0)
    const b = node('node-b', 'node-b', 'b', 320, 0)
    const edge: Edge = { id: 'edge-a-b', source: 'node-a', target: 'node-b' }

    const batch = buildLineageBatch(
      state([a, b], [edge]),
      state([{ ...a, position: { x: 5, y: 7 } }, b], [edge]),
    )

    expect(batch.create).toEqual([])
    expect(batch.delete).toEqual([])
    expect(batch.positions).toEqual([
      { ref: { node_id: 'node-a' }, x: 5, y: 7 },
      { ref: { node_id: 'node-b' }, x: 320, y: 0 },
    ])
  })
})
