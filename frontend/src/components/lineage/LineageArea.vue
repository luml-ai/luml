<template>
  <VueFlow
    :id="LINEAGE_FLOW_ID"
    :nodes="lineageStore.initialNodes"
    :edges="lineageStore.initialEdges"
    class="area"
    :default-viewport="{ zoom: 1 }"
    :min-zoom="0.2"
    :max-zoom="4"
    :delete-key-code="lineageStore.isEditable ? ['Backspace', 'Delete'] : null"
    :nodes-deletable="false"
    :nodes-draggable="lineageStore.isEditable"
    :nodes-connectable="lineageStore.isEditable"
    @node-click="onNodeClick"
  >
    <template #node-lineage="props">
      <LineageNode
        :artifactType="props.data.type"
        :title="props.data.title"
        :collectionName="props.data.collectionName"
        :variant="props.data.variant"
        :is-deleted="props.data.isDeleted"
        :deployments="props.data.deployments || []"
        :tracks="props.data.tracks || []"
        :actions-disabled="!lineageStore.canRewire"
        @replace="replaceNode(props.id)"
        @unlink="unlinkNode(props.id)"
      />
    </template>
    <template #edge-custom="edgeProps">
      <CustomArrowEdge v-bind="edgeProps" />
    </template>
    <Background pattern-color="var(--dots-color)" />
  </VueFlow>
</template>

<script setup lang="ts">
import { Background } from '@vue-flow/background'
import { VueFlow, useVueFlow, type NodeMouseEvent } from '@vue-flow/core'
import { useLineageStore } from '@/stores/lineage'
import { unlinkArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { useConfirm } from 'primevue'
import { nextTick, watch } from 'vue'
import { LINEAGE_FLOW_ID } from './lineage.data'
import type { LineageNodeData } from './lineage.interface'
import LineageNode from './LineageNode.vue'
import CustomArrowEdge from '../ui/vue-flow/CustomArrowEdge.vue'

const confirm = useConfirm()

const lineageStore = useLineageStore()
const { fitView, nodes, onNodesInitialized, viewport, setViewport } = useVueFlow(LINEAGE_FLOW_ID)

// A single node would otherwise be scaled up to the max zoom of the canvas.
const FIT_VIEW_OPTIONS = { padding: 0.2, maxZoom: 1 }
// The zoom toolbar floats over the bottom of the canvas; the fitted graph is
// shifted up so its lowest node is not hidden behind it.
const TOOLBAR_CLEARANCE = 80

let recenterPending = false

function allNodesMeasured(): boolean {
  return (
    nodes.value.length > 0 &&
    nodes.value.every((node) => node.dimensions.width > 0 && node.dimensions.height > 0)
  )
}

async function recenter(): Promise<void> {
  const fitted = await fitView(FIT_VIEW_OPTIONS)
  recenterPending = !fitted
  if (!fitted) return
  const { x, y, zoom } = viewport.value
  await setViewport({ x, y: y - TOOLBAR_CLEARANCE / 2, zoom })
}

// Vue Flow fits only the nodes it has measured, and a freshly rendered graph
// has no dimensions yet: the fit is deferred until the nodes are initialized.
onNodesInitialized(() => {
  if (recenterPending) void recenter()
})

function replaceNode(id: string) {
  lineageStore.setReplaceableArtifactId(id)
}

function unlinkNode(id: string) {
  const accept = () => {
    lineageStore.unlinkArtifact(id)
  }
  confirm.require(unlinkArtifactConfirmOptions(accept))
}

function onNodeClick({ node }: NodeMouseEvent): void {
  lineageStore.setDetailedArtifact(node.data as LineageNodeData)
}

watch(
  () => lineageStore.initialNodes,
  async (initialNodes) => {
    if (initialNodes.length === 0) return
    recenterPending = true
    await nextTick()
    if (allNodesMeasured()) await recenter()
  },
  { immediate: true, flush: 'post' },
)
</script>

<style scoped>
.area {
  height: 100%;
  width: 100%;
  --dots-color: #cdcddb;
}
[data-theme='dark'] .area {
  --dots-color: rgba(69, 69, 74, 0.7);
}
:deep(.vue-flow__node-lineage) {
  padding: 0;
}
:deep(.vue-flow__node-lineage:has(.model.main)) {
  background-color: var(--p-button-outlined-secondary-active-background);
}
:deep(.vue-flow__node-lineage:has(.experiment.main)) {
  background-color: var(--p-button-outlined-info-hover-background);
}
:deep(.vue-flow__node-lineage:has(.dataset.main)) {
  background-color: var(--p-button-text-warn-hover-background);
}
:deep(.vue-flow__node-lineage:has(.disabled)) {
  opacity: 0.6;
  border-style: dashed;
}
:deep(.vue-flow__node-lineage:has(.disabled):hover) {
  border-color: var(--p-content-border-color);
}
:deep(.vue-flow__node-lineage.selected:has(.disabled)) {
  border-color: var(--p-content-border-color);
}
</style>
