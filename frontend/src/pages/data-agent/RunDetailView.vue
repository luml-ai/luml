<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Tag, Dialog, Message } from 'primevue'
import { ArrowLeft, Play, X, GitMerge, RefreshCw } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useDataAgentStore } from '@/stores/data-agent'
import { useUploadFlow } from '@/hooks/useUploadFlow'
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket'
import { statusSeverity } from '@/components/data-agent/board/board.types'
import type { UploadReadyEvent } from '@/lib/api/data-agent/data-agent.interfaces'
import RunGraph from '@/components/data-agent/RunGraph.vue'
import NodeDetail from '@/components/data-agent/NodeDetail.vue'
import TerminalPanel from '@/components/data-agent/TerminalPanel.vue'
import MergeDialog from '@/components/data-agent/MergeDialog.vue'

const route = useRoute()
const router = useRouter()
const store = useDataAgentStore()

const uploadFlow = useUploadFlow()

const terminalSessionId = ref<string | null>(null)
const terminalLabel = ref('Terminal')
const showTerminal = ref(false)
const showMergeDialog = ref(false)

const canMerge = computed(() => {
  const run = store.selectedRun
  return run && run.status === 'succeeded' && run.best_node_id
})

const bestScore = computed(() => {
  const run = store.selectedRun
  if (!run?.best_node_id) return null
  const bestNode = store.nodes.find((n) => n.id === run.best_node_id)
  if (!bestNode) return null
  const metric = bestNode.result?.artifacts?.metric
  if (metric === undefined || metric === null) return null
  if (typeof metric === 'number') {
    return Number.isInteger(metric) ? String(metric) : metric.toFixed(4)
  }
  return String(metric)
})

const initialId = String(route.params.runId || '')
if (initialId) {
  store.selectRun(initialId)
}
useAgentWebSocket(uploadFlow)

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

    const config = run.config
    if (config.luml_collection_id && config.luml_organization_id && config.luml_orbit_id) {
      uploadFlow.resumePendingUploads(
        id,
        config.luml_collection_id,
        config.luml_organization_id,
        config.luml_orbit_id,
      )
    }
  } catch {
    // WS will provide data
  }
}

function onRetryUpload(uploadId: string) {
  const run = store.selectedRun
  if (!run?.config.luml_collection_id) return
  const entry = uploadFlow.uploads.value.get(uploadId)
  if (!entry) return
  const event: UploadReadyEvent = {
    upload_id: uploadId,
    run_id: entry.runId,
    node_id: entry.nodeId,
    file_size: 0,
    experiment_ids: [],
    collection_id: run.config.luml_collection_id!,
    organization_id: run.config.luml_organization_id!,
    orbit_id: run.config.luml_orbit_id!,
  }
  uploadFlow.retryUpload(uploadId, event)
}

async function onStartRun() {
  const run = await api.dataAgent.startRun(store.selectedRunId!)
  store.updateRun(run)
}

async function onCancelRun() {
  const run = await api.dataAgent.cancelRun(store.selectedRunId!)
  store.updateRun(run)
}


async function onMerged() {
  showMergeDialog.value = false
  const run = await api.dataAgent.getRun(store.selectedRunId!)
  store.updateRun(run)
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
              <span v-if="bestScore" class="best-score-label">Best: {{ bestScore }}</span>
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
            v-if="canMerge"
            severity="success"
            @click="showMergeDialog = true"
          >
            <GitMerge :size="14" />
            <span>Merge</span>
          </Button>
        </template>
      </div>

      <div v-if="uploadFlow.worktreesPendingMessage.value" class="upload-banner">
        <Message severity="info" :closable="false">
          {{ uploadFlow.worktreesPendingMessage.value }}
        </Message>
      </div>
      <div v-for="entry in uploadFlow.failedUploads.value" :key="entry.uploadId" class="upload-banner">
        <Message severity="error" :closable="false">
          <span>Upload failed for node {{ entry.nodeId }}: {{ entry.error }}</span>
          <Button size="small" severity="secondary" text @click="onRetryUpload(entry.uploadId)">
            <RefreshCw :size="12" />
            <span>Retry</span>
          </Button>
        </Message>
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

    <MergeDialog
      v-if="store.selectedRun"
      :visible="showMergeDialog"
      kind="run"
      :item-id="store.selectedRun.id"
      @close="showMergeDialog = false"
      @merged="onMerged"
    />

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

.best-score-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--p-green-500);
  padding: 2px 8px;
  background: color-mix(in srgb, var(--p-green-500) 12%, transparent);
  border-radius: 4px;
  white-space: nowrap;
}

.graph-area {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative;
}

.upload-banner {
  padding: 0 16px;
  flex-shrink: 0;
}

.upload-banner :deep(.p-message) {
  display: flex;
  align-items: center;
  gap: 8px;
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
