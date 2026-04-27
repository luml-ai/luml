<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Tag, Button } from 'primevue'
import { Terminal, X, TrendingUp, ExternalLink } from 'lucide-vue-next'
import { usePrismaStore } from '@/stores/prisma'
import { displayStatus } from './board/board.types'
import { api } from '@/lib/api'
import type { ArtifactContext } from '@/hooks/useUploadFlow'

const props = defineProps<{
  artifact?: ArtifactContext
}>()

const router = useRouter()
const store = usePrismaStore()

const node = computed(() => store.selectedNode)

const metric = computed(() => {
  if (node.value?.node_type !== 'run') return null
  const val = node.value?.result?.artifacts?.metric
  return val !== undefined && val !== null ? val : null
})

const resolvedArtifact = computed((): ArtifactContext | undefined => {
  if (props.artifact) return props.artifact
  const link = node.value?.result?.artifact_link
  if (link?.artifact_id) {
    return {
      artifactId: link.artifact_id,
      organizationId: link.organization_id,
      orbitId: link.orbit_id,
      collectionId: link.collection_id,
    }
  }
  return undefined
})

function formatMetric(val: any): string {
  if (typeof val === 'number') {
    return Number.isInteger(val) ? String(val) : val.toFixed(4)
  }
  return JSON.stringify(val)
}

function statusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  const map: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> = {
    queued: 'secondary',
    running: 'info',
    waiting_input: 'warn',
    succeeded: 'success',
    failed: 'danger',
    canceled: 'secondary',
  }
  return map[status] ?? 'secondary'
}

const emit = defineEmits<{
  'attach-terminal': [sessionId: string, readonly: boolean]
  close: []
}>()

async function cancelNode() {
  if (!node.value) return
  await api.dataAgent.sendNodeAction(node.value.id, 'cancel')
}

const isSessionLive = computed(() => {
  const n = node.value
  if (!n?.session_id) return false
  return n.is_alive || n.status === 'waiting_input'
})

function attachTerminal() {
  if (node.value?.session_id) {
    emit('attach-terminal', node.value.session_id, !isSessionLive.value)
  }
}

function openArtifact() {
  const ctx = resolvedArtifact.value
  if (!ctx) return
  const route = router.resolve({
    name: 'artifact',
    params: {
      organizationId: ctx.organizationId,
      id: ctx.orbitId,
      collectionId: ctx.collectionId,
      artifactId: ctx.artifactId,
    },
  })
  window.open(route.href, '_blank')
}
</script>

<template>
  <div v-if="node" class="node-detail">
    <header class="header">
      <div class="header-left">
        <h3 class="node-title">{{ node.node_type }}</h3>
        <Tag :value="displayStatus(node.status)" :severity="statusSeverity(node.status)" />
      </div>
      <Button variant="text" severity="secondary" @click="emit('close')">
        <template #icon><X :size="16" /></template>
      </Button>
    </header>

    <div class="body">
      <!-- Properties -->
      <section class="section">
        <h4 class="section-title">Properties</h4>
        <dl class="props">
          <div class="prop-row">
            <dt>ID</dt>
            <dd class="mono">{{ node.id }}</dd>
          </div>
          <div class="prop-row">
            <dt>Depth</dt>
            <dd>{{ node.depth }}</dd>
          </div>
          <div v-if="node.branch" class="prop-row">
            <dt>Branch</dt>
            <dd class="mono">{{ node.branch }}</dd>
          </div>
          <div v-if="node.worktree_path" class="prop-row">
            <dt>Worktree</dt>
            <dd class="mono truncate">{{ node.worktree_path }}</dd>
          </div>
          <div v-if="node.debug_retries > 0" class="prop-row">
            <dt>Debug retries</dt>
            <dd>{{ node.debug_retries }}</dd>
          </div>
        </dl>
      </section>

      <!-- Score -->
      <section v-if="metric !== null" class="section">
        <div class="score-card">
          <TrendingUp :size="14" class="score-icon" />
          <span class="score-label">Score</span>
          <span class="score-value">{{ formatMetric(metric) }}</span>
        </div>
      </section>

      <!-- Artifact -->
      <section v-if="resolvedArtifact" class="section">
        <h4 class="section-title">Artifact</h4>
        <button class="artifact-link" @click="openArtifact">
          <ExternalLink :size="13" />
          <span>View uploaded artifact</span>
        </button>
      </section>

      <!-- Payload -->
      <section v-if="Object.keys(node.payload).length > 0" class="section">
        <h4 class="section-title">Payload</h4>
        <pre class="json-preview">{{ JSON.stringify(node.payload, null, 2) }}</pre>
      </section>

      <!-- Result -->
      <section v-if="Object.keys(node.result).length > 0" class="section">
        <h4 class="section-title">Result</h4>
        <pre class="json-preview">{{ JSON.stringify(node.result, null, 2) }}</pre>
      </section>
    </div>

    <!-- Actions -->
    <div
      v-if="node.session_id || node.status === 'running' || node.status === 'waiting_input'"
      class="actions"
    >
      <Button
        v-if="node.session_id"
        :severity="isSessionLive ? 'info' : 'secondary'"
        @click="attachTerminal"
      >
        <Terminal :size="14" />
        <span>{{ isSessionLive ? 'Terminal' : 'View Log' }}</span>
      </Button>
      <Button
        v-if="node.status === 'running' || node.status === 'waiting_input'"
        severity="warn"
        variant="outlined"
        @click="cancelNode"
      >
        <X :size="14" />
        <span>Cancel</span>
      </Button>
    </div>
  </div>
</template>

<style scoped>
.node-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.header {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.16px;
  color: var(--p-text-color);
}

.body {
  flex: 1 1 auto;
  overflow-y: auto;
}

.section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.props {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.prop-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 13px;
}

.prop-row:last-child {
  border-bottom: none;
}

.prop-row dt {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
  margin-right: 12px;
}

.prop-row dd {
  margin: 0;
  color: var(--p-text-color);
  text-align: right;
  min-width: 0;
}

.mono {
  font-family: monospace;
  font-size: 12px;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--p-highlight-background);
  border-radius: 6px;
}

.score-icon {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.score-label {
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}

.score-value {
  color: var(--p-text-color);
  font-weight: 600;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.json-preview {
  margin: 0;
  padding: 10px 12px;
  background: var(--p-content-hover-background);
  border-radius: 6px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

.artifact-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--p-highlight-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  color: var(--p-primary-color);
  font-size: 13px;
  cursor: pointer;
  width: 100%;
}

.artifact-link:hover {
  background: var(--p-content-hover-background);
}

.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
</style>
