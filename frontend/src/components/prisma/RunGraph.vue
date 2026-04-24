<script setup lang="ts">
import { computed } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { usePrismaStore } from '@/stores/prisma'
import { computeLayout } from './utils/graphLayout'
import GraphNodeCard from './GraphNodeCard.vue'

const store = usePrismaStore()

const emit = defineEmits<{
  'open-terminal': [sessionId: string, label: string]
}>()

function handleOpenTerminal(sessionId: string, nodeType: string, nodeId: string) {
  emit('open-terminal', sessionId, `${nodeType} #${nodeId}`)
}

const layout = computed(() => computeLayout(store.nodes, store.edges))

const bestNodeId = computed(() => store.selectedRun?.best_node_id ?? null)

const flowNodes = computed(() => {
  return layout.value.nodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      selected: n.data.id === store.selectedNodeId,
      isBest: n.data.id === bestNodeId.value,
      onOpenTerminal: (sid: string) => handleOpenTerminal(sid, n.data.node_type, n.data.id),
    },
  }))
})

const flowEdges = computed(() => layout.value.edges)

function onNodeClick(event: { node: { id: string } }) {
  store.selectNode(event.node.id)
}
</script>

<template>
  <div class="graph-container">
    <VueFlow
      v-if="store.selectedRunId && store.nodes.length > 0"
      :nodes="flowNodes"
      :edges="flowEdges"
      :nodes-draggable="false"
      :nodes-connectable="false"
      fit-view-on-init
      class="agent-flow"
      @node-click="onNodeClick"
    >
      <template #node-graphNode="{ data }">
        <GraphNodeCard :data="data" :selected="data.selected" />
      </template>
      <Background pattern-color="var(--dots-color)" />
    </VueFlow>
    <div v-else-if="store.selectedRunId" class="empty">
      <span>Loading graph...</span>
    </div>
    <div v-else class="empty">
      <span>Select a workflow to view its graph</span>
    </div>
  </div>
</template>

<style scoped>
.graph-container {
  position: absolute;
  inset: 0;
}

.agent-flow {
  --dots-color: #cdcddb;
}

[data-theme='dark'] .graph-container {
  background: var(--p-content-background);
}

[data-theme='dark'] .agent-flow {
  --dots-color: rgba(69, 69, 74, 0.7);
}

/* Hide handles — nodes are not connectable */
.agent-flow :deep(.vue-flow__handle) {
  display: none;
}

/* Hide edge labels */
.agent-flow :deep(.vue-flow__edge-text) {
  display: none;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--p-text-muted-color);
  font-size: 14px;
}
</style>
