<template>
  <div
    class="wrapper"
    :class="{ 'full-screen': isFullScreen }"
    :style="isFullScreen ? undefined : { height: wrapperHeight }"
  >
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.2"
      :max-zoom="4"
      class="w-full h-full"
      @node-click="onNodeClick"
      @node-drag-stop="onNodeDragStop"
      @pane-click="flowStore.selectCell(null)"
    >
      <template #node-cell="{ data }">
        <NotebookCellNode
          :asset="data.asset"
          :cell="data.cell"
          :is-selected="data.cell.slug === flowStore.selectedCellId"
        />
      </template>
      <Background pattern-color="var(--p-content-border-color)" />
    </VueFlow>
    <Button class="zoom-button" severity="secondary" variant="text" @click="toggleFullScreen()">
      <template #icon>
        <Maximize2 :size="14" />
      </template>
    </Button>
    <NotebooksCanvasToolbar
      v-model:zoom="zoomValue"
      :can-reset-layout="flowStore.hasCanvasLayout"
      @zoom-in="zoomIn()"
      @zoom-out="zoomOut()"
      @zoom-change="onZoomChange"
      @reset-layout="resetLayout()"
    />
  </div>
  <div
    class="overlay"
    :class="{ 'opacity-100': isFullScreen, 'opacity-0 pointer-events-none': !isFullScreen }"
    @click="closeFullScreen()"
  ></div>
</template>

<script setup lang="ts">
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import { computed, nextTick, ref, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { Background } from '@vue-flow/background'
import {
  MarkerType,
  Position,
  useVueFlow,
  VueFlow,
  type Edge,
  type Node,
  type NodeMouseEvent,
} from '@vue-flow/core'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import type {
  CanvasPosition,
  CellEdge,
  CellNodeData,
  NotebookAssetInterface,
} from '@/components/notebooks/notebooks.interface'
import { useFlowStore } from '@/store/flow'
import { edgeId, edgesLeadingTo } from '@/components/notebooks/canvas.helpers'
import NotebookCellNode from '@/components/notebooks/cell/NotebookCellNode.vue'
import NotebooksCanvasToolbar from '@/components/notebooks/NotebooksCanvasToolbar.vue'

function buildNodes(
  cells: CellSummary[],
  cellEdges: CellEdge[],
  assets: NotebookAssetInterface[],
  positions: Map<string, CanvasPosition>,
): Node<CellNodeData>[] {
  const hasIncoming = new Set(cellEdges.map((edge) => edge.to))
  const hasOutgoing = new Set(cellEdges.map((edge) => edge.from))
  const assetBySlug = new Map(assets.map((asset) => [asset.id, asset]))

  const nodes: Node<CellNodeData>[] = []
  for (const cell of cells) {
    const asset = assetBySlug.get(cell.slug)
    const position = positions.get(cell.slug)
    if (!asset || !position) continue
    nodes.push({
      id: cell.slug,
      type: 'cell',
      position,
      sourcePosition: hasOutgoing.has(cell.slug) ? Position.Bottom : undefined,
      targetPosition: hasIncoming.has(cell.slug) ? Position.Top : undefined,
      data: { asset, cell },
    })
  }
  return nodes
}

function buildCanvasEdges(cellEdges: CellEdge[], selected: string | null): Edge[] {
  // The path the selected cell's result was computed along lights up with
  // it: every edge into it, and into what those came from. Lit edges go
  // last so they paint over the unlit ones they cross — SVG paints in order
  // — while every edge stays in the layer beneath the cards. A z-index
  // would lift them above the cards instead.
  const lit = edgesLeadingTo(cellEdges, selected)
  const edges: Edge[] = cellEdges.map((edge) => {
    const id = edgeId(edge)
    const isLit = lit.has(id)
    return {
      id,
      source: edge.from,
      target: edge.to,
      type: 'smoothstep',
      pathOptions: { borderRadius: 20 },
      class: isLit ? 'edge--lit' : undefined,
      markerEnd: isLit
        ? { type: MarkerType.ArrowClosed, color: 'var(--p-primary-color)' }
        : MarkerType.ArrowClosed,
    }
  })
  edges.sort((left, right) => Number(lit.has(left.id)) - Number(lit.has(right.id)))
  return edges
}

const flowStore = useFlowStore()

const nodes = computed(() =>
  buildNodes(
    flowStore.cells,
    flowStore.canvasEdges,
    flowStore.notebookCells,
    flowStore.canvasLayout,
  ),
)
const edges = computed(() => buildCanvasEdges(flowStore.canvasEdges, flowStore.selectedCellId))

const { zoomIn, zoomOut, zoomTo, viewport, setCenter, findNode, getNodes } = useVueFlow()

function onNodeDragStop() {
  const positions: Record<string, CanvasPosition> = {}
  for (const node of getNodes.value) {
    positions[node.id] = { x: node.position.x, y: node.position.y }
  }
  flowStore.saveCanvasPositions(positions)
}

function resetLayout() {
  flowStore.resetCanvasLayout()
}

function onNodeClick({ node }: NodeMouseEvent) {
  flowStore.selectCell(node.id)
}

const zoomValue = ref((viewport.value.zoom * 100).toFixed())

const isFullScreen = ref(false)

const wrapperHeight = 'calc(100vh - 211px)'

function toggleFullScreen() {
  isFullScreen.value = !isFullScreen.value
}

function closeFullScreen() {
  isFullScreen.value = false
}

onKeyStroke('Escape', () => {
  if (isFullScreen.value) {
    closeFullScreen()
  }
})

function onZoomChange(value: number) {
  zoomTo(value)
}

watch(
  () => viewport.value.zoom,
  (value) => {
    zoomValue.value = (value * 100).toFixed()
  },
)

watch(
  () => flowStore.selectedCellId,
  async (id) => {
    if (!id) return
    await nextTick()
    const node = findNode(id)
    if (!node) return
    const xPosition = node.computedPosition.x + node.dimensions.width / 2
    const yPosition = node.computedPosition.y + node.dimensions.height / 2
    setCenter(xPosition, yPosition, { zoom: 1, duration: 300 })
  },
  { immediate: true },
)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.wrapper {
  @apply p-4 border border-surface rounded-lg relative bg-(--p-content-background) transition-all duration-300;
}

.overlay {
  @apply fixed top-0 left-0 w-full h-full bg-black/30 pointer-events-none transition-opacity duration-300;
}

.zoom-button {
  @apply absolute top-5 right-5 z-1000 p-0 w-10 h-10 bg-(--p-card-background)! shadow-(--p-card-shadow);
}

.full-screen {
  @apply fixed top-4 right-4 bottom-4 left-4 z-1000 h-auto;
}
</style>

<style>
/* Vue Flow renders edges outside this component's scope. */
.vue-flow__edge .vue-flow__edge-path {
  transition:
    stroke 0.2s ease,
    stroke-width 0.2s ease;
}
.vue-flow__edge.edge--lit .vue-flow__edge-path {
  stroke: var(--p-primary-color);
  stroke-width: 2;
}
</style>
