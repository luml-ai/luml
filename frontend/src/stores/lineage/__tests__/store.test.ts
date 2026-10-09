import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import type { LineageGraph } from '@/lib/api/lineage/interfaces'

const apiMocks = vi.hoisted(() => ({
  getGraph: vi.fn(),
  applyChanges: vi.fn(),
}))

const route = vi.hoisted(() => ({
  params: {
    organizationId: 'org',
    id: 'orbit',
    collectionId: 'models',
    artifactId: 'model',
  },
}))

const artifacts = vi.hoisted(() => ({ currentArtifact: null as Artifact | null }))
const routeHarness = vi.hoisted(() => ({
  current: null as null | { params: { artifactId: string } },
}))

const flowHarness = vi.hoisted(() => ({
  current: null as null | {
    nodes: { value: unknown[] }
    edges: { value: unknown[] }
    connectHandlers: ((connection: { source: string; target: string }) => void)[]
    nodeChangeHandlers: ((changes: { type: string }[]) => void)[]
    edgeChangeHandlers: ((changes: { type: string }[]) => void)[]
  },
}))

vi.mock('@/lib/api', () => ({ api: { lineage: apiMocks } }))
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  // The store derives the current artifact from the route: it has to react
  // to a change of the route parameters.
  routeHarness.current = reactive(route)
  return { useRoute: () => routeHarness.current }
})
vi.mock('@/stores/artifacts', () => ({ useArtifactsStore: () => artifacts }))
vi.mock('@vue-flow/core', async () => {
  const { ref } = await import('vue')
  const nodes = ref<unknown[]>([])
  const edges = ref<unknown[]>([])
  const connectHandlers: ((connection: { source: string; target: string }) => void)[] = []
  const nodeChangeHandlers: ((changes: { type: string }[]) => void)[] = []
  const edgeChangeHandlers: ((changes: { type: string }[]) => void)[] = []
  flowHarness.current = {
    nodes,
    edges,
    connectHandlers,
    nodeChangeHandlers,
    edgeChangeHandlers,
  }

  return {
    useVueFlow: vi.fn(() => ({
      nodes,
      edges,
      setNodes: (value: unknown[]) => {
        nodes.value = value
      },
      setEdges: (value: unknown[]) => {
        edges.value = value
      },
      addEdges: (value: Record<string, unknown>) => {
        edges.value = [...edges.value, { id: `draft-${edges.value.length}`, ...value }]
        edgeChangeHandlers.forEach((handler) => handler([{ type: 'add' }]))
      },
      onConnect: (handler: (connection: { source: string; target: string }) => void) => {
        connectHandlers.push(handler)
      },
      onNodesChange: (handler: (changes: { type: string }[]) => void) => {
        nodeChangeHandlers.push(handler)
      },
      onEdgesChange: (handler: (changes: { type: string }[]) => void) => {
        edgeChangeHandlers.push(handler)
      },
    })),
  }
})

import { useVueFlow } from '@vue-flow/core'
import { LINEAGE_FLOW_ID } from '@/components/lineage/lineage.data'
import { LEVEL_WIDTH, ROW_HEIGHT } from '../layout'
import { useLineageStore } from '..'

function artifact(id: string, collectionId = 'models', collectionName = 'Models'): Artifact {
  return {
    id,
    name: id,
    collection_id: collectionId,
    collection_name: collectionName,
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.uploaded,
    deployments: [],
    tracks: [],
  } as unknown as Artifact
}

function emptyGraph(truncated = false, depth: number | null = null): LineageGraph {
  return {
    nodes: [],
    edges: [],
    focal_artifact_id: 'model',
    depth,
    truncated,
  }
}

function connectedGraph(): LineageGraph {
  return {
    focal_artifact_id: 'model',
    depth: 2,
    truncated: false,
    nodes: [
      {
        id: 'node-model',
        artifact_id: 'model',
        type: ArtifactTypeEnum.model,
        name: 'model',
        collection_name: 'Models',
        x: 0,
        y: 0,
        is_deleted: false,
        data: artifact('model'),
      },
      {
        id: 'node-output',
        artifact_id: 'output',
        type: ArtifactTypeEnum.model,
        name: 'output',
        collection_name: 'Models',
        x: 300,
        y: 50,
        is_deleted: false,
        data: artifact('output'),
      },
    ],
    edges: [
      {
        id: 'edge-output',
        source: 'node-model',
        target: 'node-output',
        created_by_user: 'Ada',
        created_via: 'ui',
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
  }
}

function flow() {
  if (!flowHarness.current) throw new Error('Flow harness was not initialized')
  return flowHarness.current
}

function openArtifact(id: string): void {
  if (!routeHarness.current) throw new Error('Route harness was not initialized')
  routeHarness.current.params.artifactId = id
  artifacts.currentArtifact = {
    ...artifact(id),
    collection: { id: 'models', name: 'Models' },
  } as Artifact
}

describe('lineage store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getGraph.mockReset()
    apiMocks.applyChanges.mockReset()
    openArtifact('model')
    flow().nodes.value = []
    flow().edges.value = []
    flow().connectHandlers.length = 0
    flow().nodeChangeHandlers.length = 0
    flow().edgeChangeHandlers.length = 0
  })

  it('always loads the whole graph without a depth and clears edit history', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph(true))
    const store = useLineageStore()

    await store.load()
    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'))
    expect(store.history).toHaveLength(1)

    await store.load()

    expect(apiMocks.getGraph).toHaveBeenCalledWith('org', 'orbit', 'model')
    expect(apiMocks.getGraph).toHaveBeenCalledTimes(2)
    expect(store.initialNodes.map((node) => node.id)).toEqual(['artifact:model'])
    expect(store.truncated).toBe(true)
    expect(store.history).toEqual([])
  })

  it('keeps edits and canvas state when a batch save fails', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    apiMocks.applyChanges.mockRejectedValue(new Error('conflict'))
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    expect(store.unconnectedArtifactsCount).toBe(1)
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })
    expect(store.usedArtifactsIds).toEqual(['model', 'dataset'])
    expect(store.unconnectedArtifactsCount).toBe(0)

    await expect(store.save()).rejects.toThrow('conflict')
    expect(store.history).toHaveLength(2)
    expect(flow().nodes.value).toHaveLength(2)
    expect(flow().edges.value).toHaveLength(1)
  })

  it('saves one diff batch and reloads the graph on success', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    apiMocks.applyChanges.mockResolvedValue({ created: [], deleted: [] })
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })
    await store.save()

    expect(apiMocks.applyChanges).toHaveBeenCalledWith(
      'org',
      'orbit',
      expect.objectContaining({
        create: [
          {
            source: { artifact_id: 'dataset' },
            target: { artifact_id: 'model' },
          },
        ],
        delete: [],
      }),
    )
    expect(apiMocks.getGraph).toHaveBeenCalledTimes(2)
    expect(store.history).toEqual([])
  })

  it('forgets the edits before reloading so a failed reload cannot resend the batch', async () => {
    apiMocks.getGraph
      .mockResolvedValueOnce(emptyGraph())
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(emptyGraph())
    apiMocks.applyChanges.mockResolvedValue({ created: [], deleted: [] })
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })

    await expect(store.save()).rejects.toThrow('could not be reloaded')
    expect(store.hasEdits).toBe(false)
    expect(flow().edges.value).toHaveLength(1)

    await store.save()
    expect(apiMocks.applyChanges).toHaveBeenCalledTimes(1)
  })

  it('locks the canvas while a save is in flight and ignores repeated saves', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    let finishSave: (result: { created: never[]; deleted: never[] }) => void = () => undefined
    apiMocks.applyChanges.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishSave = resolve
        }),
    )
    const store = useLineageStore()
    await store.load()
    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'), { x: -260, y: 0 })
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'artifact:model' })

    const saving = store.save()
    expect(store.isSaving).toBe(true)
    expect(store.isEditable).toBe(false)

    // Edits made meanwhile would be missing from the submitted batch and
    // overwritten by the reload: the canvas refuses them instead.
    store.addArtifact(artifact('late', 'datasets', 'Datasets'))
    flow().connectHandlers[0]({ source: 'artifact:model', target: 'artifact:late' })
    store.goBack()
    expect(flow().nodes.value).toHaveLength(2)
    expect(flow().edges.value).toHaveLength(1)
    expect(store.history).toHaveLength(2)

    await store.save()
    expect(apiMocks.applyChanges).toHaveBeenCalledTimes(1)

    finishSave({ created: [], deleted: [] })
    await saving
    expect(store.isSaving).toBe(false)
    expect(store.isEditable).toBe(true)
    expect(store.hasEdits).toBe(false)
    expect(apiMocks.getGraph).toHaveBeenCalledTimes(2)
  })

  it('clears and locks the canvas when the graph of the next artifact fails to load', async () => {
    apiMocks.getGraph
      .mockResolvedValueOnce(connectedGraph())
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(emptyGraph())
    const store = useLineageStore()
    await store.load()
    expect(flow().nodes.value).toHaveLength(2)
    expect(store.isEditable).toBe(true)

    // The old graph belongs to another artifact as soon as the route moves on.
    openArtifact('next')
    expect(store.isEditable).toBe(false)

    await expect(store.load()).rejects.toThrow('network')
    expect(store.loadFailed).toBe(true)
    expect(store.loadedArtifactId).toBeNull()
    expect(store.isEditable).toBe(false)
    expect(flow().nodes.value).toEqual([])
    expect(flow().edges.value).toEqual([])
    expect(store.hasEdits).toBe(false)

    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'))
    expect(flow().nodes.value).toEqual([])
    await store.save()
    expect(apiMocks.applyChanges).not.toHaveBeenCalled()

    await store.load()
    expect(store.loadFailed).toBe(false)
    expect(store.loadedArtifactId).toBe('next')
    expect(store.isEditable).toBe(true)
    expect(store.initialNodes.map((node) => node.id)).toEqual(['artifact:next'])
  })

  it('lets moving the focal node of an empty graph be undone but not saved', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    const store = useLineageStore()
    await store.load()

    const focal = flow().nodes.value[0] as { position: { x: number; y: number } }
    focal.position = { x: 120, y: 40 }
    flow().nodeChangeHandlers[0]([{ type: 'position' }])

    expect(store.history).toHaveLength(1)
    expect(store.hasEdits).toBe(false)
    await store.save()
    expect(apiMocks.applyChanges).not.toHaveBeenCalled()

    store.goBack()
    expect(focal.position).toEqual({ x: 120, y: 40 })
    expect((flow().nodes.value[0] as { position: { x: number; y: number } }).position).toEqual({
      x: 0,
      y: 0,
    })
  })

  it('refuses unlink and replace on a truncated graph but still allows exact edits', async () => {
    const graph = connectedGraph()
    graph.truncated = true
    apiMocks.getGraph.mockResolvedValue(graph)
    const store = useLineageStore()
    await store.load()
    expect(store.isEditable).toBe(true)
    expect(store.canRewire).toBe(false)

    // Hidden connections of the node would survive and bring it back.
    store.unlinkArtifact('node-output')
    store.setReplaceableArtifactId('node-output')
    store.replaceArtifact(artifact('replacement'))
    expect((flow().nodes.value as { id: string }[]).map((node) => node.id)).toEqual([
      'node-model',
      'node-output',
    ])
    expect(store.hasEdits).toBe(false)

    // Adding a connection touches only what is on the canvas.
    store.addArtifact(artifact('dataset', 'datasets', 'Datasets'))
    flow().connectHandlers[0]({ source: 'artifact:dataset', target: 'node-model' })
    expect(store.hasEdits).toBe(true)
  })

  it('places a linked artifact in the first free slot next to the focal node', async () => {
    apiMocks.getGraph.mockResolvedValue(emptyGraph())
    const store = useLineageStore()
    await store.load()

    store.addArtifact(artifact('first', 'datasets', 'Datasets'))
    store.addArtifact(artifact('second', 'datasets', 'Datasets'))

    const placed = (flow().nodes.value as { id: string; position: { x: number; y: number } }[])
      .filter((node) => node.id !== 'artifact:model')
      .map((node) => node.position)
    expect(placed).toEqual([
      { x: LEVEL_WIDTH, y: 0 },
      { x: LEVEL_WIDTH, y: ROW_HEIGHT },
    ])
  })

  it('drops a deleted node once its last connection is removed', async () => {
    const graph = connectedGraph()
    graph.nodes[1] = { ...graph.nodes[1], artifact_id: null, is_deleted: true, data: null }
    apiMocks.getGraph.mockResolvedValue(graph)
    const store = useLineageStore()
    await store.load()
    expect(flow().nodes.value).toHaveLength(2)

    flow().edges.value = []
    flow().edgeChangeHandlers[0]([{ type: 'remove' }])
    await nextTick()

    expect((flow().nodes.value as { id: string }[]).map((node) => node.id)).toEqual(['node-model'])
    expect(store.unconnectedArtifactsCount).toBe(0)
    expect(store.hasEdits).toBe(true)
  })

  it('records a keyboard-removed edge and sends it after the orphaned node is removed', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    apiMocks.applyChanges.mockResolvedValue({ created: [], deleted: [] })
    const store = useLineageStore()
    await store.load()

    flow().edges.value = []
    flow().edgeChangeHandlers[0]([{ type: 'remove' }])
    expect(store.hasEdits).toBe(true)
    expect(store.unconnectedArtifactsCount).toBe(1)

    store.unlinkArtifact('node-output')
    await store.save()

    expect(apiMocks.applyChanges).toHaveBeenCalledWith(
      'org',
      'orbit',
      expect.objectContaining({ create: [], delete: ['edge-output'] }),
    )
  })

  it('records moving, reset positions, unlink, and undo as edits', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    const output = flow().nodes.value.find(
      (node) => (node as { id: string }).id === 'node-output',
    ) as { position: { x: number; y: number } }
    output.position = { x: 400, y: 80 }
    flow().nodeChangeHandlers[0]([{ type: 'position' }])
    expect(store.history).toHaveLength(1)

    store.resetPositions()
    expect(store.history).toHaveLength(2)
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 320, y: 0 })

    store.goBack()
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 400, y: 80 })

    store.unlinkArtifact('node-output')
    expect(flow().nodes.value).toHaveLength(1)
    expect(flow().edges.value).toEqual([])
    expect(store.history).toHaveLength(2)
  })

  it('treats movement as an edit and undo restores the loaded position', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    const output = flow().nodes.value.find(
      (node) => (node as { id: string }).id === 'node-output',
    ) as { position: { x: number; y: number } }
    output.position = { x: 400, y: 80 }
    flow().nodeChangeHandlers[0]([{ type: 'position' }])

    expect(store.history).toHaveLength(1)

    store.goBack()

    expect(store.history).toEqual([])
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 300, y: 50 })
  })

  it('resets saved positions with no prior edit and undo restores them', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    store.resetPositions()

    expect(store.history).toHaveLength(1)
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 320, y: 0 })

    store.goBack()
    expect(
      (
        flow().nodes.value.find((node) => (node as { id: string }).id === 'node-output') as {
          position: { x: number; y: number }
        }
      ).position,
    ).toEqual({ x: 300, y: 50 })
  })

  it('discards edits and restores the loaded graph before leaving', async () => {
    apiMocks.getGraph.mockResolvedValue(connectedGraph())
    const store = useLineageStore()
    await store.load()

    store.unlinkArtifact('node-output')
    expect(store.hasEdits).toBe(true)
    expect(flow().nodes.value).toHaveLength(1)

    store.discardChanges()

    expect(store.hasEdits).toBe(false)
    expect(flow().nodes.value).toHaveLength(2)
    expect(flow().edges.value).toHaveLength(1)
  })

  it('shares one flow instance with the canvas through the lineage flow id', () => {
    useLineageStore()

    expect(vi.mocked(useVueFlow)).toHaveBeenCalledWith(LINEAGE_FLOW_ID)
  })
})
