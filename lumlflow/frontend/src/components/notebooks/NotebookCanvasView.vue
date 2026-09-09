<template>
  <div class="wrapper" :class="{ 'full-screen': isFullScreen }">
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.2"
      :max-zoom="4"
      class="w-full h-full"
      @node-click="onNodeClick"
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
      @zoom-in="zoomIn()"
      @zoom-out="zoomOut()"
      @zoom-change="onZoomChange"
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
  CellEdge,
  CellNodeData,
  NotebookAssetInterface,
} from '@/components/notebooks/notebooks.interface'
import { useFlowStore } from '@/store/flow'
import NotebookCellNode from '@/components/notebooks/cell/NotebookCellNode.vue'
import NotebooksCanvasToolbar from '@/components/notebooks/NotebooksCanvasToolbar.vue'
import {
  NOTEBOOK_CANVAS_LEVEL_HEIGHT,
  NOTEBOOK_CANVAS_NODE_WIDTH,
} from '@/components/notebooks/notebooks.const'

function producerOf(reference: string): string {
  const dot = reference.indexOf('.')
  return dot === -1 ? reference : reference.slice(0, dot)
}

function buildEdges(cells: CellSummary[]): CellEdge[] {
  const slugs = new Set(cells.map((cell) => cell.slug))
  const edges: CellEdge[] = []
  for (const cell of cells) {
    for (const [input, reference] of Object.entries(cell.consumes)) {
      const from = producerOf(reference)
      if (slugs.has(from) && from !== cell.slug) edges.push({ from, to: cell.slug, input })
    }
  }
  return edges
}

function buildLevels(cells: CellSummary[], edges: CellEdge[]): Map<string, number> {
  const parents = new Map<string, string[]>(cells.map((cell) => [cell.slug, []]))
  for (const edge of edges) parents.get(edge.to)?.push(edge.from)

  const levels = new Map<string, number>()
  function levelOf(slug: string, guard: Set<string>): number {
    if (levels.has(slug)) return levels.get(slug) as number
    if (guard.has(slug)) return 0
    guard.add(slug)
    const cellParents = parents.get(slug) ?? []
    const level =
      cellParents.length === 0
        ? 0
        : 1 + Math.max(...cellParents.map((parent) => levelOf(parent, guard)))
    levels.set(slug, level)
    return level
  }
  for (const cell of cells) levelOf(cell.slug, new Set())
  return levels
}

function buildCanvas(
  cells: CellSummary[],
  assets: NotebookAssetInterface[],
): { nodes: Node<CellNodeData>[]; edges: Edge[] } {
  const cellEdges = buildEdges(cells)
  const levels = buildLevels(cells, cellEdges)
  const hasIncoming = new Set(cellEdges.map((edge) => edge.to))
  const hasOutgoing = new Set(cellEdges.map((edge) => edge.from))
  const assetBySlug = new Map(assets.map((asset) => [asset.id, asset]))

  const layers = new Map<number, string[]>()
  for (const cell of cells) {
    const level = levels.get(cell.slug) ?? 0
    const bucket = layers.get(level) ?? []
    bucket.push(cell.slug)
    layers.set(level, bucket)
  }

  const nodes: Node<CellNodeData>[] = []
  for (const [level, slugs] of layers) {
    const width = slugs.length * NOTEBOOK_CANVAS_NODE_WIDTH
    slugs.forEach((slug, index) => {
      const asset = assetBySlug.get(slug)
      const cell = cells.find((candidate) => candidate.slug === slug)
      if (!asset || !cell) return
      nodes.push({
        id: slug,
        type: 'cell',
        position: {
          x: index * NOTEBOOK_CANVAS_NODE_WIDTH - width / 2 + NOTEBOOK_CANVAS_NODE_WIDTH / 2,
          y: level * NOTEBOOK_CANVAS_LEVEL_HEIGHT,
        },
        sourcePosition: hasOutgoing.has(slug) ? Position.Bottom : undefined,
        targetPosition: hasIncoming.has(slug) ? Position.Top : undefined,
        data: { asset, cell },
      })
    })
  }

  const edges: Edge[] = cellEdges.map((edge) => ({
    id: `e-${edge.from}-${edge.to}-${edge.input}`,
    source: edge.from,
    target: edge.to,
    type: 'smoothstep',
    pathOptions: { borderRadius: 20 },
    markerEnd: MarkerType.ArrowClosed,
  }))

  return { nodes, edges }
}

const flowStore = useFlowStore()

const canvas = computed(() => buildCanvas(flowStore.cells, flowStore.notebookCells))
const nodes = computed(() => canvas.value.nodes)
const edges = computed(() => canvas.value.edges)

const { zoomIn, zoomOut, zoomTo, viewport, setCenter, findNode } = useVueFlow()

function onNodeClick({ node }: NodeMouseEvent) {
  flowStore.selectCell(node.id)
}

const zoomValue = ref((viewport.value.zoom * 100).toFixed())

const isFullScreen = ref(false)

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
  @apply h-[calc(100vh-211px)] p-4 border border-surface rounded-lg relative bg-(--p-content-background) transition-all duration-300;
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
