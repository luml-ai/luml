<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Tag, Dialog } from 'primevue'
import { ArrowLeft, Play, X, RotateCcw, Trash2 } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useDataAgentStore } from '@/stores/data-agent'
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket'
import { statusSeverity } from '@/components/data-agent/board/board.types'
import RunGraph from '@/components/data-agent/RunGraph.vue'
import NodeDetail from '@/components/data-agent/NodeDetail.vue'
import TerminalPanel from '@/components/data-agent/TerminalPanel.vue'

const route = useRoute()
const router = useRouter()
const store = useDataAgentStore()

const terminalSessionId = ref<string | null>(null)
const terminalLabel = ref('Terminal')
const showTerminal = ref(false)

const initialId = String(route.params.runId || '')
if (initialId) {
  store.selectRun(initialId)
}
useAgentWebSocket()

async function loadInitialData() {
  const id = String(route.params.runId || '')
  if (!id) return
  store.selectRun(id)
  try {
    const [graph, run] = await Promise.all([
      api.dataAgent.getRunGraph(id),
      api.dataAgent.getRun(id),
    ])
    store.updateRun(run)
    store.applySnapshot({ ...graph, run })
  } catch {
    // WS will provide data
  }
}

async function onStartRun() {
  const run = await api.dataAgent.startRun(store.selectedRunId!)
  store.updateRun(run)
}

async function onCancelRun() {
  const run = await api.dataAgent.cancelRun(store.selectedRunId!)
  store.updateRun(run)
}

async function onRestartRun() {
  const run = await api.dataAgent.restartRun(store.selectedRunId!)
  store.updateRun(run)
  store.selectRun(run.id)
}

async function onDeleteRun() {
  await api.dataAgent.deleteRun(store.selectedRunId!)
  store.removeRun(store.selectedRunId!)
  goBack()
}

function openTerminalDialog(sessionId: string, label?: string) {
  terminalSessionId.value = sessionId
  terminalLabel.value = label ?? 'Terminal'
  showTerminal.value = true
}

function closeTerminal() {
  showTerminal.value = false
  terminalSessionId.value = null
}

function onAttachTerminal(sessionId: string) {
  const node = store.selectedNode
  const label = node ? `${node.node_type} #${node.id}` : 'Terminal'
  openTerminalDialog(sessionId, label)
}

function onGraphOpenTerminal(sessionId: string, label: string) {
  openTerminalDialog(sessionId, label)
}

function closeNodeDetail() {
  store.selectNode(null)
}

function goBack() {
  router.push({ name: 'data-agent-board' })
}

onMounted(() => {
  loadInitialData()
})

onUnmounted(() => {
  store.selectRun(null)
})
</script>

<template>
  <div class="run-detail-view">
    <div class="detail-content">
      <div class="content-header">
        <Button variant="text" severity="secondary" @click="goBack">
          <template #icon><ArrowLeft :size="16" /></template>
        </Button>
        <template v-if="store.selectedRun">
          <div class="header-info">
            <div class="header-info-top">
              <span class="content-title">{{ store.selectedRun.name }}</span>
              <Tag :value="store.selectedRun.status" :severity="statusSeverity(store.selectedRun.status)" />
            </div>
            <span v-if="store.selectedRun.objective" class="run-objective">{{ store.selectedRun.objective }}</span>
          </div>
          <Button
            v-if="store.selectedRun.status === 'pending'"
            severity="success"
            @click="onStartRun"
          >
            <Play :size="14" />
            <span>Start</span>
          </Button>
          <Button
            v-if="store.selectedRun.status === 'running'"
            severity="warn"
            @click="onCancelRun"
          >
            <X :size="14" />
            <span>Cancel</span>
          </Button>
          <Button
            v-if="['failed', 'canceled', 'succeeded'].includes(store.selectedRun.status)"
            severity="warn"
            @click="onRestartRun"
          >
            <RotateCcw :size="14" />
            <span>Restart</span>
          </Button>
          <Button
            v-if="store.selectedRun.status !== 'running'"
            severity="warn"
            variant="outlined"
            @click="onDeleteRun"
          >
            <Trash2 :size="14" />
            <span>Delete</span>
          </Button>
        </template>
      </div>

      <div class="graph-area">
        <RunGraph v-if="store.selectedRunId" @open-terminal="onGraphOpenTerminal" />
        <div v-else class="graph-loading">Loading graph...</div>
      </div>
    </div>

    <Transition name="slide-right">
      <Teleport to="body">
        <div
          v-if="store.selectedNodeId"
          class="sidebar-wrapper"
          @click.self="closeNodeDetail"
        >
          <div class="node-sidebar">
            <NodeDetail
              @attach-terminal="onAttachTerminal"
              @close="closeNodeDetail"
            />
          </div>
        </div>
      </Teleport>
    </Transition>

    <Dialog
      :visible="showTerminal"
      :header="terminalLabel"
      :draggable="true"
      :modal="false"
      :style="{ width: '960px', height: '580px' }"
      :content-style="{
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
      }"
      class="terminal-dialog"
      position="bottom"
      @update:visible="!$event && closeTerminal()"
    >
      <TerminalPanel
        v-if="terminalSessionId"
        :session-id="terminalSessionId"
        :active="showTerminal"
        :task-name="terminalLabel"
      />
    </Dialog>
  </div>
</template>

<style scoped>
.run-detail-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding-top: 12px;
}

.detail-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-card-background);
}

.content-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.header-info-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.content-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.run-objective {
  font-size: 12px;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.graph-area {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative;
}

.graph-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.sidebar-wrapper {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 10;
}

.node-sidebar {
  position: fixed;
  top: 80px;
  bottom: 60px;
  right: 16px;
  width: 100%;
  max-width: 420px;
  padding: 24px 20px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.5s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}
</style>
