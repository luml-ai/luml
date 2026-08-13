<template>
  <div class="card" data-testid="traces-panel">
    <div class="head">
      <div>
        <p class="section-title small">Traces</p>
        <p class="section-subtitle">
          Recent inference calls in this window — the raw request log behind every metric.
        </p>
      </div>
      <span
        class="local-badge"
        title="Fetched directly from the Satellite, never through the Platform"
      >
        <ShieldCheck :size="13" />
        local only
      </span>
    </div>

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No inference calls in this window"
      empty-detail="Recent prediction requests will appear here once the deployment serves traffic."
    />

    <template v-else-if="traces">
      <div class="table-scroll">
        <table class="traces">
          <thead>
            <tr>
              <th>Time</th>
              <th>Request</th>
              <th>Features</th>
              <th>Prediction</th>
              <th class="num">Latency</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in traces.rows"
              :key="row.event_id"
              class="row"
              data-testid="trace-row"
              tabindex="0"
              role="button"
              :aria-label="`Open call ${row.event_id}`"
              @click="$emit('open', row.event_id)"
              @keydown.enter.prevent="$emit('open', row.event_id)"
              @keydown.space.prevent="$emit('open', row.event_id)"
            >
              <td class="nowrap">{{ formatTimestamp(row.ts) ?? '—' }}</td>
              <td class="mono id">{{ row.event_id }}</td>
              <td class="mono summary">{{ row.features_summary ?? '—' }}</td>
              <td class="mono summary">{{ row.prediction ?? '—' }}</td>
              <td class="num nowrap">{{ Math.round(row.latency_ms) }} ms</td>
              <td>
                <span class="status" :class="statusClass(row.status_code)">{{ row.status }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pager">
        <span class="range">{{ rangeLabel }}</span>
        <div class="buttons">
          <button
            type="button"
            data-testid="traces-prev"
            :disabled="traces.offset <= 0"
            @click="$emit('page', traces.offset - traces.limit)"
          >
            Prev
          </button>
          <button
            type="button"
            data-testid="traces-next"
            :disabled="!hasNext"
            @click="$emit('page', traces.offset + traces.limit)"
          >
            Next
          </button>
        </div>
      </div>
    </template>

    <TraceDetailDialog
      v-if="openTraceId"
      :event-id="openTraceId"
      :trace="traceDetail"
      :status="traceDetailStatus"
      @close="$emit('close-trace')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ShieldCheck } from 'lucide-vue-next'
import type { TraceDetail, TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { formatTimestamp } from '@/lib/format'
import StateBlock from '@/components/StateBlock.vue'
import TraceDetailDialog from '@/components/TraceDetailDialog.vue'

const props = defineProps<{
  traces: TracesResponse | null
  status: LoadStatus
  openTraceId: string | null
  traceDetail: TraceDetail | null
  traceDetailStatus: LoadStatus
}>()
defineEmits<{ page: [number]; open: [string]; 'close-trace': [] }>()

const view = computed(() => sectionView(props.status, props.traces?.state))

const rangeLabel = computed(() => {
  const traces = props.traces
  if (!traces || traces.total === 0) return 'No calls'
  if (traces.rows.length === 0) return `0 of ${traces.total}`
  const first = traces.offset + 1
  const last = traces.offset + traces.rows.length
  return `${first}–${last} of ${traces.total}`
})

const hasNext = computed(() => {
  const traces = props.traces
  return traces ? traces.offset + traces.limit < traces.total : false
})

function statusClass(statusCode: number): string {
  return statusCode >= 500 ? 'err' : statusCode >= 400 ? 'warn' : 'ok'
}
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--luml-space-4);
  margin-bottom: var(--luml-space-4);
}
.section-title.small {
  font-size: var(--luml-text-base);
}
.local-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: var(--luml-radius-pill);
  background: var(--luml-surface-100);
  color: var(--luml-fg-muted);
  font-size: 11px;
  font-weight: 500;
}
.table-scroll {
  overflow-x: auto;
}
.traces {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.traces th {
  text-align: left;
  padding: 8px 12px;
  color: var(--luml-fg-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
}
.traces td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--luml-surface-100);
  color: var(--luml-fg);
  vertical-align: top;
}
.traces .num {
  text-align: right;
}
.row {
  cursor: pointer;
}
.row:hover,
.row:focus-visible {
  background: var(--luml-bg-hover);
  outline: none;
}
.nowrap {
  white-space: nowrap;
}
.id {
  color: var(--luml-fg-muted);
}
.summary {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.status {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--luml-radius-pill);
  font-size: 12px;
  font-weight: 500;
}
.status.ok {
  background: var(--luml-success-tint-bg);
  color: var(--luml-success-tint-fg);
}
.status.warn {
  background: var(--luml-warn-tint-bg);
  color: var(--luml-warn-tint-fg);
}
.status.err {
  background: var(--luml-danger-tint-bg);
  color: var(--luml-danger-tint-fg);
}
.pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--luml-space-4);
}
.range {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.buttons {
  display: flex;
  gap: var(--luml-space-2);
}
.buttons button {
  padding: 6px 14px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.buttons button:disabled {
  opacity: 0.5;
  cursor: default;
}
.buttons button:not(:disabled):hover {
  background: var(--luml-bg-hover);
}
</style>
