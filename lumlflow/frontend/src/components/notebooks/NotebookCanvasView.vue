<template>
  <div class="wrapper" :class="{ 'full-screen': isFullScreen }">
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      fit-view-on-init
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.2"
      :max-zoom="4"
      class="w-full h-full"
    >
      <template #node-cell>
        <NotebookCellNode />
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
import { ref, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { Background } from '@vue-flow/background'
import { MarkerType, Position, useVueFlow, VueFlow, type Edge, type Node } from '@vue-flow/core'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import NotebookCellNode from '@/components/notebooks/cell/NotebookCellNode.vue'
import NotebooksCanvasToolbar from '@/components/notebooks/NotebooksCanvasToolbar.vue'

const nodes = ref<Node[]>([
  {
    id: '1',
    type: 'cell',
    position: { x: 0, y: 0 },
    sourcePosition: Position.Bottom,
  },
  {
    id: '2',
    type: 'cell',
    position: { x: -250, y: 550 },
    targetPosition: Position.Top,
  },
  {
    id: '3',
    type: 'cell',
    position: { x: 250, y: 550 },
    targetPosition: Position.Top,
  },
])

const edges = ref<Edge[]>([
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    type: 'smoothstep',
    pathOptions: { borderRadius: 20 },
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'e1-3',
    source: '1',
    target: '3',
    type: 'smoothstep',
    pathOptions: { borderRadius: 20 },
    markerEnd: MarkerType.ArrowClosed,
  },
])

const { zoomIn, zoomOut, zoomTo, viewport } = useVueFlow()

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
