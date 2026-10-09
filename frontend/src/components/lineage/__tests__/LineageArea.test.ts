import { flushPromises, shallowMount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { LINEAGE_FLOW_ID } from '../lineage.data'
import type { LineageNodeData } from '../lineage.interface'
import LineageArea from '../LineageArea.vue'

const harness = vi.hoisted(() => ({
  store: null as null | {
    initialNodes: unknown[]
    initialEdges: unknown[]
    isEditable: boolean
    setDetailedArtifact: ReturnType<typeof vi.fn>
    setReplaceableArtifactId: ReturnType<typeof vi.fn>
    unlinkArtifact: ReturnType<typeof vi.fn>
  },
}))

type MeasuredNode = { dimensions: { width: number; height: number } }

const flow = vi.hoisted(() => ({
  useVueFlow: vi.fn(),
  fitView: vi.fn().mockResolvedValue(true),
  setViewport: vi.fn().mockResolvedValue(undefined),
  viewport: { value: { x: 0, y: 0, zoom: 1 } },
  nodes: { value: [] as { dimensions: { width: number; height: number } }[] },
  nodesInitializedHandlers: [] as (() => void)[],
}))

vi.mock('@/stores/lineage', async () => {
  const { reactive } = await import('vue')
  harness.store = reactive({
    initialNodes: [] as unknown[],
    initialEdges: [] as unknown[],
    isEditable: true,
    setDetailedArtifact: vi.fn(),
    setReplaceableArtifactId: vi.fn(),
    unlinkArtifact: vi.fn(),
  })
  return { useLineageStore: () => harness.store }
})
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useConfirm: () => ({ require: vi.fn() }) }
})
vi.mock('@vue-flow/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vue-flow/core')>()
  flow.useVueFlow.mockImplementation(() => ({
    fitView: flow.fitView,
    setViewport: flow.setViewport,
    viewport: flow.viewport,
    nodes: flow.nodes,
    onNodesInitialized: (handler: () => void) => {
      flow.nodesInitializedHandlers.push(handler)
    },
  }))
  return { ...actual, useVueFlow: flow.useVueFlow }
})

const VueFlowStub = defineComponent({
  name: 'VueFlow',
  props: {
    id: { type: String, default: '' },
    deleteKeyCode: { type: null, default: () => [] },
    nodesDeletable: { type: Boolean, default: true },
    nodesDraggable: { type: Boolean, default: true },
    nodesConnectable: { type: Boolean, default: true },
  },
  emits: ['nodeClick'],
  template: '<div />',
})

function nodeData(isDeleted = false): LineageNodeData {
  return {
    nodeId: 'node',
    artifactId: isDeleted ? null : 'artifact',
    collectionId: isDeleted ? null : 'collection',
    collectionName: 'Collection',
    isDeleted,
    type: ArtifactTypeEnum.model,
    title: 'Model',
    variant: isDeleted ? 'disabled' : 'default',
    data: null,
  }
}

function measured(): MeasuredNode {
  return { dimensions: { width: 220, height: 70 } }
}

function unmeasured(): MeasuredNode {
  return { dimensions: { width: 0, height: 0 } }
}

function nodesInitialized(): void {
  flow.nodesInitializedHandlers.forEach((handler) => handler())
}

let wrapper: VueWrapper | null = null

function mountArea() {
  wrapper = shallowMount(LineageArea, {
    global: {
      stubs: {
        VueFlow: VueFlowStub,
        Background: true,
        LineageNode: true,
        CustomArrowEdge: true,
      },
    },
  })
  return wrapper
}

describe('LineageArea', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (!harness.store) throw new Error('Store harness was not initialized')
    harness.store.initialNodes = []
    harness.store.initialEdges = []
    harness.store.isEditable = true
    flow.nodes.value = []
    flow.nodesInitializedHandlers = []
    flow.viewport.value = { x: 0, y: 0, zoom: 1 }
    flow.fitView.mockResolvedValue(true)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('binds the canvas and its helpers to the shared lineage flow instance', () => {
    const canvas = mountArea().findComponent(VueFlowStub)

    expect(flow.useVueFlow).toHaveBeenCalledWith(LINEAGE_FLOW_ID)
    expect(canvas.props('id')).toBe(LINEAGE_FLOW_ID)
  })

  it('lets both delete keys remove edges but never nodes', () => {
    const canvas = mountArea().findComponent(VueFlowStub)

    expect(canvas.props('deleteKeyCode')).toEqual(['Backspace', 'Delete'])
    expect(canvas.props('nodesDeletable')).toBe(false)
  })

  it('locks moving, connecting, and keyboard deletion while the store is not editable', async () => {
    const canvas = mountArea().findComponent(VueFlowStub)
    if (!harness.store) throw new Error('Store harness was not initialized')
    expect(canvas.props('nodesDraggable')).toBe(true)
    expect(canvas.props('nodesConnectable')).toBe(true)

    harness.store.isEditable = false
    await canvas.vm.$nextTick()

    expect(canvas.props('nodesDraggable')).toBe(false)
    expect(canvas.props('nodesConnectable')).toBe(false)
    expect(canvas.props('deleteKeyCode')).toBeNull()
  })

  it('opens details for live and deleted nodes', async () => {
    const canvas = mountArea().findComponent(VueFlowStub)
    const live = nodeData()
    if (!harness.store) throw new Error('Store harness was not initialized')

    canvas.vm.$emit('nodeClick', { node: { data: live }, event: new MouseEvent('click') })
    await canvas.vm.$nextTick()
    expect(harness.store.setDetailedArtifact).toHaveBeenCalledWith(live)

    harness.store.setDetailedArtifact.mockClear()
    const deleted = nodeData(true)
    canvas.vm.$emit('nodeClick', { node: { data: deleted }, event: new MouseEvent('click') })
    await canvas.vm.$nextTick()
    expect(harness.store.setDetailedArtifact).toHaveBeenCalledWith(deleted)
  })

  it('recenters right away when the loaded nodes are already measured', async () => {
    mountArea()
    if (!harness.store) throw new Error('Store harness was not initialized')

    flow.nodes.value = [measured(), measured()]
    harness.store.initialNodes = [{ id: 'focal' }, { id: 'input' }]
    await flushPromises()

    expect(flow.fitView).toHaveBeenCalledTimes(1)
    expect(flow.fitView).toHaveBeenCalledWith({ padding: 0.2, maxZoom: 1 })
  })

  it('waits for freshly rendered nodes to be measured before recentering', async () => {
    mountArea()
    if (!harness.store) throw new Error('Store harness was not initialized')

    flow.nodes.value = [measured(), unmeasured()]
    harness.store.initialNodes = [{ id: 'focal' }, { id: 'input' }]
    await flushPromises()
    expect(flow.fitView).not.toHaveBeenCalled()

    nodesInitialized()
    await flushPromises()
    expect(flow.fitView).toHaveBeenCalledTimes(1)
    expect(flow.fitView).toHaveBeenCalledWith({ padding: 0.2, maxZoom: 1 })

    // Nodes added while editing initialize too; that must not move the canvas.
    nodesInitialized()
    await flushPromises()
    expect(flow.fitView).toHaveBeenCalledTimes(1)
  })

  it('lifts the fitted graph above the floating toolbar', async () => {
    mountArea()
    if (!harness.store) throw new Error('Store harness was not initialized')
    flow.viewport.value = { x: 12, y: 30, zoom: 0.5 }

    flow.nodes.value = [measured()]
    harness.store.initialNodes = [{ id: 'focal' }]
    await flushPromises()

    expect(flow.setViewport).toHaveBeenCalledWith({ x: 12, y: -10, zoom: 0.5 })
  })

  it('retries the fit on initialization when the canvas could not fit yet', async () => {
    mountArea()
    if (!harness.store) throw new Error('Store harness was not initialized')

    flow.fitView.mockResolvedValueOnce(false)
    flow.nodes.value = [measured()]
    harness.store.initialNodes = [{ id: 'focal' }]
    await flushPromises()
    expect(flow.fitView).toHaveBeenCalledTimes(1)

    nodesInitialized()
    await flushPromises()
    expect(flow.fitView).toHaveBeenCalledTimes(2)
  })
})
