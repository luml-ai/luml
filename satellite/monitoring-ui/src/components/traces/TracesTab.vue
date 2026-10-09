<template>
  <section class="traces-tab" data-testid="traces-tab">
    <div class="intro">
      <p class="section-title">Traces</p>
      <p class="section-subtitle">
        Recent inference calls in the selected window — the raw request log behind every metric.
      </p>
    </div>

    <TracesPanel
      :traces="traces"
      :status="status"
      :open-trace-id="openTraceId"
      :trace-detail="traceDetail"
      :trace-detail-status="traceDetailStatus"
      :new-count="newCount"
      :sort-key="sortKey"
      :sort-order="sortOrder"
      @page="$emit('page', $event)"
      @open="$emit('open', $event)"
      @close-trace="$emit('close-trace')"
      @show-latest="$emit('show-latest')"
      @sort="$emit('sort', $event)"
    />
  </section>
</template>

<script setup lang="ts">
import type { SortOrder, TraceDetail, TraceSortKey, TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import TracesPanel from '@/components/TracesPanel.vue'

withDefaults(
  defineProps<{
    traces: TracesResponse | null
    status: LoadStatus
    openTraceId: string | null
    traceDetail: TraceDetail | null
    traceDetailStatus: LoadStatus
    newCount?: number
    sortKey?: TraceSortKey
    sortOrder?: SortOrder
  }>(),
  { newCount: 0, sortKey: 'ts', sortOrder: 'desc' },
)

defineEmits<{
  page: [number]
  open: [string]
  'close-trace': []
  'show-latest': []
  sort: [TraceSortKey]
}>()
</script>

<style scoped>
.traces-tab {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
</style>
