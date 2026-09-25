import { h, nextTick, ref, type VNode } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { VueFlow, type Edge, type Node, type VueFlowStore } from '@vue-flow/core'

import FlowCanvas, {
  type CanvasSessionState,
  type CellNodeData,
} from '@/flow/workbench/components/canvas/FlowCanvas.vue'
import {
  createCanvasLayout,
  updateCanvasLayout,
} from '@/flow/workbench/components/canvas/canvasLayout'
import type { FlowCell } from '@/flow/workbench/model/types'

function cell(uid: string, order: string, consumesByInput: Record<string, string> = {}): FlowCell {
  return {
    uid,
    slug: uid,
    doc: '',
    consumes: Object.values(consumesByInput),
    consumesByInput,
    params: {},
    source: '',
    outputs: [],
    status: 'materialized',
    authoredStep: Number(order),
    order,
  }
}

const canvasProps = (cells: FlowCell[], selectedSlug: string | null = null) => ({
  cells,
  branch: 'main',
  selectedSlug,
  tintedSlugs: new Set<string>(),
  preflights: {},
})

function cardSlot({ cell: shown }: { cell: FlowCell }): VNode {
  return h('button', { class: `control-${shown.slug}` }, shown.slug)
}

function drawnNodes(wrapper: VueWrapper): Node<CellNodeData>[] {
  return wrapper.findComponent(VueFlow).props('nodes') as Node<CellNodeData>[]
}

function positionOf(wrapper: VueWrapper, uid: string): { x: number; y: number } {
  const node = drawnNodes(wrapper).find((candidate) => candidate.data?.cell.uid === uid)
  expect(node, `missing canvas node ${uid}`).toBeTruthy()
  return node!.position
}

describe('canvas layout', () => {
  it('top-aligns columns and orders each column by parent barycenter then key', () => {
    const firstRoot = cell('first-root', '1')
    const secondRoot = cell('second-root', '2')
    const lower = cell('lower', '3', { input: 'second-root.value' })
    const early = cell('early', '4', { input: 'first-root.value' })
    const late = cell('late', '5', { input: 'first-root.value' })
    const layout = createCanvasLayout([firstRoot, secondRoot, lower, early, late])

    expect(layout.positions['first-root'].y).toBe(0)
    expect(layout.positions.early.y).toBe(0)
    expect(layout.positions.early.y).toBeLessThan(layout.positions.late.y)
    expect(layout.positions.late.y).toBeLessThan(layout.positions.lower.y)
  })

  it('keeps existing nodes still and puts a parentless anchored add below its predecessor', () => {
    const load = cell('load', '1')
    const prepare = cell('prepare', '2', { rows: 'load.rows' })
    const train = cell('train', '3', { rows: 'prepare.rows' })
    const score = cell('score', '4', { model: 'train.model' })
    const before = createCanvasLayout([load, prepare, train, score])
    const note = cell('note', '3.5')
    const after = updateCanvasLayout(before, [load, prepare, train, note, score])

    for (const existing of [load, prepare, train, score]) {
      expect(after.positions[existing.uid!]).toEqual(before.positions[existing.uid!])
    }
    expect(after.positions.note.x).toBe(before.positions.train.x)
    expect(
      Object.entries(after.positions)
        .filter(([, position]) => position.x === after.positions.train.x)
        .sort(([, left], [, right]) => left.y - right.y)
        .map(([uid]) => uid),
    ).toEqual(['train', 'note'])

    const renamedTrain = { ...train, slug: 'fit' }
    const renamedScore = {
      ...score,
      consumes: ['fit.model'],
      consumesByInput: { model: 'fit.model' },
    }
    const renamed = updateCanvasLayout(after, [load, prepare, renamedTrain, note, renamedScore])
    expect(renamed.positions.train).toEqual(after.positions.train)
    expect(renamed.positions.score).toEqual(after.positions.score)
  })

  it('recomputes every position only when tidied or existing wiring changes', () => {
    const root = cell('root', '1')
    const later = cell('later', '4', { rows: 'root.rows' })
    const before = createCanvasLayout([root, later])
    const earlier = cell('earlier', '3', { rows: 'root.rows' })
    const incremental = updateCanvasLayout(before, [root, later, earlier])
    const tidied = createCanvasLayout([root, later, earlier])

    expect(incremental.positions.later).toEqual(before.positions.later)
    expect(incremental.positions.earlier.y).toBeGreaterThan(incremental.positions.later.y)
    expect(tidied.positions.earlier.y).toBeLessThan(tidied.positions.later.y)

    const movedUp = updateCanvasLayout(tidied, [root, { ...later, order: '2' }, earlier])
    expect(movedUp.positions.earlier).toEqual(tidied.positions.earlier)
    expect(movedUp.positions.later.y).toBeLessThan(movedUp.positions.earlier.y)

    const rewired = cell('later', '4')
    expect(updateCanvasLayout(incremental, [root, rewired, earlier]).positions).toEqual(
      createCanvasLayout([root, rewired, earlier]).positions,
    )
  })

  it('fits once, tidies on request, pans minimally, and names parallel edges by input', async () => {
    const root = cell('root', '1')
    const later = cell('later', '4', { rows: 'root.rows' })
    const wrapper = mount(FlowCanvas, {
      props: canvasProps([root, later], 'root'),
      slots: { card: cardSlot },
    })
    const fitView = vi.fn().mockResolvedValue(true)
    const panBy = vi.fn().mockReturnValue(true)
    const store = {
      fitView,
      panBy,
      getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
      dimensions: ref({ width: 500, height: 700 }),
      findNode: () => undefined,
    } as unknown as VueFlowStore
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', store)
    wrapper.findComponent(VueFlow).vm.$emit('nodesInitialized', [])
    await nextTick()

    const earlier = cell('earlier', '3', { rows: 'root.rows' })
    await wrapper.setProps({ cells: [root, later, earlier] })
    expect(positionOf(wrapper, 'later')).toEqual({ x: 600, y: 0 })
    expect(positionOf(wrapper, 'earlier').y).toBeGreaterThan(0)
    expect(fitView).toHaveBeenCalledTimes(1)

    await wrapper.get('button[aria-label="tidy layout"]').trigger('click')
    expect(positionOf(wrapper, 'earlier')).toEqual({ x: 600, y: 0 })
    expect(positionOf(wrapper, 'later').y).toBeGreaterThan(0)

    await wrapper.setProps({ selectedSlug: 'later' })
    expect(panBy).toHaveBeenCalledTimes(1)
    expect(panBy.mock.calls[0][0]).toMatchObject({ x: expect.any(Number), y: 0 })
    expect(panBy.mock.calls[0][0].x).toBeLessThan(0)
    expect(fitView).toHaveBeenCalledTimes(1)

    const consumer = cell('consumer', '5', {
      model: 'later.result',
      baseline: 'later.result',
    })
    await wrapper.setProps({ cells: [root, later, earlier, consumer] })
    const edges = wrapper.findComponent(VueFlow).props('edges') as Edge[]
    const parallel = edges.filter((edge) => edge.source === 'later' && edge.target === 'consumer')
    expect(parallel.map((edge) => edge.id)).toEqual([
      'later->consumer:model',
      'later->consumer:baseline',
    ])

    wrapper.unmount()
  })

  it('restores incremental positions and the viewport for the session', async () => {
    const root = cell('root', '1')
    const later = cell('later', '4', { rows: 'root.rows' })
    const earlier = cell('earlier', '3', { rows: 'root.rows' })
    const wrapper = mount(FlowCanvas, {
      props: canvasProps([root, later]),
      slots: { card: cardSlot },
    })
    const viewport = { x: -180, y: -40, zoom: 0.8 }
    const store = {
      fitView: vi.fn().mockResolvedValue(true),
      getViewport: () => viewport,
    } as unknown as VueFlowStore
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', store)
    wrapper.findComponent(VueFlow).vm.$emit('nodesInitialized', [])
    await wrapper.setProps({ cells: [root, later, earlier] })
    const before = drawnNodes(wrapper).map((node) => ({ id: node.id, position: node.position }))
    wrapper.unmount()

    const states = wrapper.emitted('update:state') as [CanvasSessionState][]
    const state = states.at(-1)![0]
    const restored = mount(FlowCanvas, {
      props: { ...canvasProps([root, later, earlier]), state },
      slots: { card: cardSlot },
    })
    expect(drawnNodes(restored).map((node) => ({ id: node.id, position: node.position }))).toEqual(
      before,
    )

    const fitView = vi.fn().mockResolvedValue(true)
    const setViewport = vi.fn().mockResolvedValue(true)
    const restoredStore = {
      fitView,
      setViewport,
      getViewport: () => viewport,
    } as unknown as VueFlowStore
    restored.findComponent(VueFlow).vm.$emit('paneReady', restoredStore)
    restored.findComponent(VueFlow).vm.$emit('nodesInitialized', [])
    await nextTick()

    expect(fitView).not.toHaveBeenCalled()
    expect(setViewport).toHaveBeenCalledWith(viewport)
    restored.unmount()
  })
})
