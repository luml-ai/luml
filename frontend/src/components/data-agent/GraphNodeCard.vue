<script setup lang="ts">
import { computed } from 'vue'
import { Terminal } from 'lucide-vue-next'
import type { RunNode } from '@/lib/api/data-agent/data-agent.interfaces'
import { useDataAgentStore } from '@/stores/data-agent'
import { displayStatus } from './board/board.types'

const props = defineProps<{
  data: RunNode & { onOpenTerminal?: (sessionId: string) => void; isBest?: boolean }
  selected: boolean
}>()

const store = useDataAgentStore()

const statusColors: Record<string, string> = {
  queued: 'var(--p-surface-400)',
  running: 'var(--p-blue-500)',
  waiting_input: 'var(--p-yellow-500)',
  succeeded: 'var(--p-green-500)',
  failed: 'var(--p-red-500)',
  canceled: 'var(--p-surface-400)',
}

const storeNode = computed(() => store.nodes.find((n) => n.id === props.data.id))
const statusColor = computed(() => statusColors[props.data.status] ?? 'var(--p-surface-400)')
const isRunning = computed(() => props.data.status === 'running')
const isWaitingInput = computed(() => props.data.status === 'waiting_input')
const hasTerminal = computed(() => isRunning.value || isWaitingInput.value)

const isRunNode = computed(() => props.data.node_type === 'run')
const metric = computed(() => {
  if (!isRunNode.value) return null
  const node = storeNode.value ?? props.data
  const val = node?.result?.artifacts?.metric
  return val !== undefined && val !== null ? val : null
})

function formatMetric(val: any): string {
  if (typeof val === 'number') {
    return Number.isInteger(val) ? String(val) : val.toFixed(4)
  }
  return JSON.stringify(val)
}

function openTerminal(e: MouseEvent) {
  e.stopPropagation()
  const sid = storeNode.value?.session_id ?? props.data.session_id
  if (sid && props.data.onOpenTerminal) {
    props.data.onOpenTerminal(sid)
  }
}
</script>

<template>
  <div class="node-body">
    <header class="header">
      <div class="header-left">
        <span class="status-dot" :style="{ background: statusColor }" />
        <h3 class="header-title">{{ data.node_type }}</h3>
        <span v-if="data.isBest" class="best-tag">best</span>
      </div>
      <Terminal
        v-if="hasTerminal"
        :size="14"
        class="terminal-icon"
        title="Open terminal"
        @pointerdown.stop
        @click="openTerminal"
      />
    </header>
    <div class="info">
      <span class="status-label">{{ displayStatus(data.status) }}</span>
    </div>
    <div v-if="metric !== null" class="score" :class="{ 'score-best': data.isBest }">
      <span class="score-label">score</span>
      <span class="score-value">{{ formatMetric(metric) }}</span>
    </div>
  </div>
</template>

<style scoped>
.node-body {
  width: 180px;
  padding-bottom: 8px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
}

.header-left {
  display: flex;
  gap: 6px;
  align-items: center;
}

.header-title {
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 500;
  margin: 0;
}

.best-tag {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-green-500);
  background: color-mix(in srgb, var(--p-green-500) 12%, transparent);
  padding: 1px 5px;
  border-radius: 3px;
  line-height: 1.4;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.info {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.status-label {
  text-transform: capitalize;
}

.score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding: 4px 6px;
  background: var(--p-highlight-background);
  border-radius: 4px;
  font-size: 12px;
  min-height: 28px;
}

.score-label {
  color: var(--p-text-muted-color);
  font-size: 11px;
  text-transform: uppercase;
  font-weight: 500;
}

.score-value {
  color: var(--p-text-color);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.score-best {
  background: color-mix(in srgb, var(--p-green-500) 12%, transparent);
}

.score-best .score-value {
  color: var(--p-green-500);
}

.terminal-icon {
  color: var(--p-primary-color);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: background 0.15s;
}

.terminal-icon:hover {
  background: var(--p-highlight-background);
}
</style>
