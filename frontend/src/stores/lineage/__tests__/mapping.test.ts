import { describe, expect, it } from 'vitest'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import type { LineageGraph } from '@/lib/api/lineage/interfaces'
import { artifactCanvasNodeId, mapGraphToCanvas, type LineageFocalArtifact } from '../mapping'

function artifact(id: string, name: string, collectionName: string): Artifact {
  return {
    id,
    name,
    collection_id: `collection-${id}`,
    collection_name: collectionName,
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.uploaded,
    deployments: [],
    tracks: [],
  } as unknown as Artifact
}

function focalArtifact(): LineageFocalArtifact {
  return {
    ...artifact('model', 'Model', 'stale collection name'),
    collection: { id: 'models', name: 'Models' },
  }
}

describe('mapGraphToCanvas', () => {
  it('synthesizes the focal node for an empty graph using the details collection', () => {
    const graph: LineageGraph = {
      nodes: [],
      edges: [],
      focal_artifact_id: 'model',
      depth: 2,
      truncated: false,
    }

    const canvas = mapGraphToCanvas(graph, focalArtifact())

    expect(canvas.edges).toEqual([])
    expect(canvas.nodes).toHaveLength(1)
    expect(canvas.nodes[0]).toMatchObject({
      id: 'artifact:model',
      position: { x: 0, y: 0 },
      data: {
        nodeId: null,
        artifactId: 'model',
        collectionId: 'models',
        collectionName: 'Models',
        variant: 'main',
        isDeleted: false,
      },
    })
  })

  it('preserves saved positions and lays out missing nodes beside placed neighbours', () => {
    const model = artifact('model', 'Model', 'Models')
    const dataset = artifact('dataset', 'Dataset', 'Datasets')
    const experiment = artifact('experiment', 'Experiment', 'Experiments')
    const output = artifact('output', 'Output', 'Models')
    const graph: LineageGraph = {
      focal_artifact_id: 'model',
      depth: 2,
      truncated: false,
      nodes: [
        {
          id: 'node-model',
          artifact_id: 'model',
          type: ArtifactTypeEnum.model,
          name: 'Model',
          collection_name: 'Models',
          x: 0,
          y: 0,
          is_deleted: false,
          data: model,
        },
        {
          id: 'node-dataset',
          artifact_id: 'dataset',
          type: ArtifactTypeEnum.dataset,
          name: 'Dataset',
          collection_name: 'Datasets',
          x: -320,
          y: 0,
          is_deleted: false,
          data: dataset,
        },
        {
          id: 'node-experiment',
          artifact_id: 'experiment',
          type: ArtifactTypeEnum.experiment,
          name: 'Experiment',
          collection_name: 'Experiments',
          x: null,
          y: null,
          is_deleted: false,
          data: experiment,
        },
        {
          id: 'node-output',
          artifact_id: 'output',
          type: ArtifactTypeEnum.model,
          name: 'Output',
          collection_name: 'Models',
          x: 320,
          y: 0,
          is_deleted: false,
          data: output,
        },
      ],
      edges: [
        {
          id: 'edge-dataset',
          source: 'node-dataset',
          target: 'node-model',
          created_by_user: 'Ada',
          created_via: 'ui',
          created_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'edge-experiment',
          source: 'node-experiment',
          target: 'node-model',
          created_by_user: 'Ada',
          created_via: 'ui',
          created_at: '2026-01-01T00:00:01Z',
        },
        {
          id: 'edge-output',
          source: 'node-model',
          target: 'node-output',
          created_by_user: 'Ada',
          created_via: 'ui',
          created_at: '2026-01-01T00:00:02Z',
        },
      ],
    }

    const canvas = mapGraphToCanvas(graph, focalArtifact())
    const positions = Object.fromEntries(canvas.nodes.map((node) => [node.id, node.position]))

    expect(positions).toEqual({
      'node-model': { x: 0, y: 0 },
      'node-dataset': { x: -320, y: 0 },
      'node-experiment': { x: -320, y: 120 },
      'node-output': { x: 320, y: 0 },
    })
    expect(
      canvas.edges.map(({ id, source, target, type }) => ({ id, source, target, type })),
    ).toEqual([
      {
        id: 'edge-dataset',
        source: 'node-dataset',
        target: 'node-model',
        type: 'custom',
      },
      {
        id: 'edge-experiment',
        source: 'node-experiment',
        target: 'node-model',
        type: 'custom',
      },
      {
        id: 'edge-output',
        source: 'node-model',
        target: 'node-output',
        type: 'custom',
      },
    ])
    expect(canvas.nodes.find((node) => node.id === 'node-model')?.data.nodeId).toBe('node-model')
  })

  it('maps deleted nodes from their copied fields without an artifact id', () => {
    const graph: LineageGraph = {
      focal_artifact_id: 'model',
      depth: 1,
      truncated: false,
      nodes: [
        {
          id: 'node-model',
          artifact_id: 'model',
          type: ArtifactTypeEnum.model,
          name: 'Model',
          collection_name: 'Models',
          x: 0,
          y: 0,
          is_deleted: false,
          data: artifact('model', 'Model', 'Models'),
        },
        {
          id: 'node-deleted',
          artifact_id: null,
          type: ArtifactTypeEnum.dataset,
          name: 'Old dataset',
          collection_name: 'Archive',
          x: -320,
          y: 0,
          is_deleted: true,
          data: null,
        },
      ],
      edges: [
        {
          id: 'edge-1',
          source: 'node-deleted',
          target: 'node-model',
          created_by_user: 'Ada',
          created_via: 'api',
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
    }

    const deleted = mapGraphToCanvas(graph, focalArtifact()).nodes.find(
      (node) => node.id === 'node-deleted',
    )

    expect(deleted?.data).toMatchObject({
      nodeId: 'node-deleted',
      artifactId: null,
      collectionId: null,
      collectionName: 'Archive',
      title: 'Old dataset',
      variant: 'disabled',
      isDeleted: true,
      data: null,
    })
  })
})

describe('artifactCanvasNodeId', () => {
  it('names nodes added during the editing session by artifact id', () => {
    expect(artifactCanvasNodeId('abc')).toBe('artifact:abc')
  })
})
