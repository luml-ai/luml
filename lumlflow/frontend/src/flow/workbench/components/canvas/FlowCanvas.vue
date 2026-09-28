<template>
  <VueFlow
    :nodes="nodes"
    :edges="edges"
    :nodes-draggable="false"
    :nodes-connectable="false"
    :min-zoom="0.12"
    :max-zoom="1.25"
    class="h-full"
    @node-click="onNodeClick"
    @nodes-initialized="onNodesInitialized"
    @pane-ready="onPaneReady"
  >
    <template #node-cell="{ data }">
      <CellFlowNode :tinted="data.tinted" @press="selectFromCard(data.cell.slug)">
        <!--
          The card is the caller's: the fixture path takes the fallback below,
          a live session hands in one bound to the daemon. Either way it is the
          same CellCard at the same density — the canvas owns the placement.
        -->
        <slot name="card" :cell="data.cell" :selected="data.selected" :preflight="data.preflight">
          <CellCard
            :cell="data.cell"
            density="canvas"
            :selected="data.selected"
            :preflight="data.preflight"
            @expand="emit('expand', data.cell.slug)"
            @run="emit('run', data.cell.slug, $event)"
            @stop="emit('stop', data.cell.slug)"
            @rename="emit('rename', data.cell.slug)"
            @delete="emit('delete', data.cell.slug)"
            @duplicate="emit('duplicate', data.cell.slug)"
            @copy-context="emit('copy-context', data.cell.slug)"
            @resolve-conflict="emit('resolve-conflict', data.cell.slug, $event)"
            @edit="emit('edit', data.cell.slug, $event)"
          />
        </slot>
      </CellFlowNode>
    </template>
    <Background :gap="26" pattern-color="var(--p-surface-300)" />
    <Controls :show-interactive="false" position="bottom-right">
      <ControlButton aria-label="tidy layout" title="tidy layout" @click="tidy">
        <LayoutGrid :size="14" />
      </ControlButton>
    </Controls>
  </VueFlow>
</template>

<script lang="ts">
import type { ViewportTransform } from '@vue-flow/core'
import type { FlowCell, Preflight } from '../../model/types'
import type { CanvasLayout } from './canvasLayout'

/** What a node carries: the cell it draws and how this view stands to it. */
export interface CellNodeData {
  cell: FlowCell
  selected: boolean
  /** Transitive-staleness filter is ON and this cell is transitively stale. */
  tinted: boolean
  preflight?: Preflight
}

export interface CanvasSessionState {
  layout: CanvasLayout
  fitted: boolean
  viewport?: ViewportTransform
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { VueFlow, type Edge, type Node, type VueFlowStore } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { ControlButton, Controls } from '@vue-flow/controls'
import { LayoutGrid } from 'lucide-vue-next'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { sliceEdges } from '../../model/registry'
import CellCard from '../card/CellCard.vue'
import CellFlowNode from './CellFlowNode.vue'
import {
  cellIdentity,
  createCanvasLayout,
  NODE_HEIGHT,
  NODE_WIDTH,
  updateCanvasLayout,
} from './canvasLayout'

/**
 * The canvas view: the branch slice as a left-to-right DAG whose edges are the
 * declared consumes wiring — the graph on screen is the graph the scheduler
 * runs. Nodes host the same CellCard the notebook uses, at canvas density.
 */
const props = defineProps<{
  cells: FlowCell[]
  branch: string
  selectedSlug: string | null
  tintedSlugs: Set<string>
  preflights: Record<string, Preflight | undefined>
  state?: CanvasSessionState | null
}>()

const emit = defineEmits<{
  'update:state': [state: CanvasSessionState]
  select: [slug: string]
  expand: [slug: string]
  run: [slug: string, payload: { force: boolean }]
  stop: [slug: string]
  rename: [slug: string]
  delete: [slug: string]
  duplicate: [slug: string]
  'copy-context': [slug: string]
  'resolve-conflict': [slug: string, choice: 'overwrite' | 'fork']
  edit: [slug: string, payload: { source: string }]
}>()

const layout = shallowRef(
  props.state
    ? updateCanvasLayout(props.state.layout, props.cells)
    : createCanvasLayout(props.cells),
)
let fitted = props.state?.fitted ?? false
let viewport = props.state?.viewport

function updateState(): void {
  emit('update:state', { layout: layout.value, fitted, viewport })
}

function setLayout(next: CanvasLayout): void {
  layout.value = next
  updateState()
}

watch(
  () => props.cells,
  (cells) => {
    setLayout(updateCanvasLayout(layout.value, cells))
  },
)

function tidy(): void {
  setLayout(createCanvasLayout(props.cells))
}

const nodes = computed<Node<CellNodeData>[]>(() =>
  props.cells.map((cell) => ({
    id: cellIdentity(cell),
    type: 'cell',
    position: layout.value.positions[cellIdentity(cell)] ?? { x: 0, y: 0 },
    style: { width: `${NODE_WIDTH}px` },
    data: {
      cell,
      selected: cell.slug === props.selectedSlug,
      tinted: props.tintedSlugs.has(cell.slug),
      preflight: props.preflights[cell.slug],
    },
  })),
)

const edges = computed<Edge[]>(() => {
  const bySlug = new Map(props.cells.map((cell) => [cell.slug, cell]))
  return sliceEdges(props.cells).map(({ from, to, input }) => ({
    id: `${cellIdentity(bySlug.get(from)!)}->${cellIdentity(bySlug.get(to)!)}:${input}`,
    source: cellIdentity(bySlug.get(from)!),
    target: cellIdentity(bySlug.get(to)!),
    type: 'smoothstep',
    animated: bySlug.get(to)?.status === 'running',
    style: { strokeWidth: 1.5, opacity: 0.55 },
  }))
})

const instance = shallowRef<VueFlowStore | null>(null)
let pressedSlug: string | null = null
let nodesReady = false
let viewportInitialized = false
const VIEWPORT_PADDING = 24

function panSelectedIntoView(): void {
  const slug = props.selectedSlug
  const store = instance.value
  const cell = props.cells.find((candidate) => candidate.slug === slug)
  if (!cell || !store) return
  const position = layout.value.positions[cellIdentity(cell)]
  const { width, height } = store.dimensions.value
  if (!position || width <= 0 || height <= 0) return

  const { x, y, zoom } = store.getViewport()
  const node = store.findNode(cellIdentity(cell))
  const nodeWidth = node?.dimensions.width || NODE_WIDTH
  const nodeHeight = node?.dimensions.height || NODE_HEIGHT
  const left = x + position.x * zoom
  const right = left + nodeWidth * zoom
  const top = y + position.y * zoom
  const bottom = top + nodeHeight * zoom
  if (right > 0 && left < width && bottom > 0 && top < height) return

  const deltaX =
    right <= 0 ? VIEWPORT_PADDING - right : left >= width ? width - VIEWPORT_PADDING - left : 0
  const deltaY =
    bottom <= 0 ? VIEWPORT_PADDING - bottom : top >= height ? height - VIEWPORT_PADDING - top : 0
  store.panBy({ x: deltaX, y: deltaY })
}

function onPaneReady(store: VueFlowStore): void {
  instance.value = store
  initializeViewport()
}

function onNodesInitialized(): void {
  nodesReady = true
  initializeViewport()
}

function initializeViewport(): void {
  const store = instance.value
  if (viewportInitialized || !nodesReady || !store) return
  viewportInitialized = true
  if (fitted) {
    if (viewport) void store.setViewport(viewport).catch(() => undefined)
    return
  }
  fitted = true
  updateState()
  void store.fitView({ padding: 0.08, maxZoom: 0.9 }).catch(() => undefined)
}

onBeforeUnmount(() => {
  const store = instance.value
  if (store) viewport = store.getViewport()
  updateState()
})

watch(
  () => props.selectedSlug,
  (slug) => {
    const keepStill = slug !== null && slug === pressedSlug
    pressedSlug = null
    if (!keepStill) panSelectedIntoView()
  },
)

function onNodeClick(event: { node: { data: CellNodeData } }): void {
  selectFromCard(event.node.data.cell.slug)
}

function selectFromCard(slug: string): void {
  if (slug === props.selectedSlug || slug === pressedSlug) return
  pressedSlug = slug
  emit('select', slug)
}
</script>

<style>
.vue-flow__node-cell {
  cursor: pointer;
}
</style>
