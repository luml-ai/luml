<template>
  <VueFlow
    :nodes="nodes"
    :edges="edges"
    :nodes-draggable="false"
    :nodes-connectable="false"
    :min-zoom="0.12"
    :max-zoom="1.25"
    fit-view-on-init
    class="h-full"
    @node-click="onNodeClick"
    @pane-ready="onPaneReady"
  >
    <template #node-cell="{ data }">
      <CellFlowNode :tinted="data.tinted">
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
            :branch="branch"
            :preflight="data.preflight"
            @expand="emit('expand', data.cell.slug)"
            @run="emit('run', data.cell.slug, $event)"
            @stop="emit('stop', data.cell.slug)"
            @rename="emit('rename', data.cell.slug)"
            @delete="emit('delete', data.cell.slug)"
            @duplicate="emit('duplicate', data.cell.slug)"
            @send-to-agent="emit('send-to-agent', data.cell.slug, $event)"
            @resolve-conflict="emit('resolve-conflict', data.cell.slug, $event)"
            @edit="emit('edit', data.cell.slug, $event)"
          />
        </slot>
      </CellFlowNode>
    </template>
    <Background :gap="26" pattern-color="var(--p-surface-300)" />
    <Controls :show-interactive="false" position="bottom-right" />
  </VueFlow>
</template>

<script lang="ts">
import type { FlowCell, Preflight } from '../../model/types'

/** What a node carries: the cell it draws and how this view stands to it. */
export interface CellNodeData {
  cell: FlowCell
  selected: boolean
  /** Transitive-staleness filter is ON and this cell is transitively stale. */
  tinted: boolean
  preflight?: Preflight
}
</script>

<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import { VueFlow, type Edge, type Node, type VueFlowStore } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { sliceEdges } from '../../model/registry'
import CellCard from '../card/CellCard.vue'
import CellFlowNode from './CellFlowNode.vue'
import { layoutSlice, NODE_WIDTH } from './canvasLayout'

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
}>()

const emit = defineEmits<{
  select: [slug: string]
  expand: [slug: string]
  run: [slug: string, payload: { force: boolean }]
  stop: [slug: string]
  rename: [slug: string]
  delete: [slug: string]
  duplicate: [slug: string]
  'send-to-agent': [slug: string, payload: string]
  'resolve-conflict': [slug: string, choice: 'overwrite' | 'fork']
  edit: [slug: string, payload: { source: string }]
}>()

const positions = computed(() => layoutSlice(props.cells))

const nodes = computed<Node<CellNodeData>[]>(() =>
  props.cells.map((cell) => ({
    id: cell.slug,
    type: 'cell',
    position: positions.value[cell.slug] ?? { x: 0, y: 0 },
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
  return sliceEdges(props.cells).map(({ from, to }) => ({
    id: `${from}->${to}`,
    source: from,
    target: to,
    type: 'smoothstep',
    animated: bySlug.get(to)?.status === 'running',
    style: { strokeWidth: 1.5, opacity: 0.55 },
  }))
})

// --- focus the selected node -----------------------------------------------

const instance = shallowRef<VueFlowStore | null>(null)

function focusSelected(animate: boolean): void {
  const slug = props.selectedSlug
  const store = instance.value
  if (!slug || !store || !props.cells.some((cell) => cell.slug === slug)) return
  void store
    .fitView({ nodes: [slug], padding: 0.4, maxZoom: 0.9, duration: animate ? 400 : 0 })
    .catch(() => undefined)
}

function onPaneReady(store: VueFlowStore): void {
  instance.value = store
  focusSelected(false)
}

watch(
  () => props.selectedSlug,
  () => focusSelected(true),
)

function onNodeClick(event: { node: { id: string } }): void {
  emit('select', event.node.id)
}
</script>

<style>
.vue-flow__node-cell {
  cursor: pointer;
}
</style>
