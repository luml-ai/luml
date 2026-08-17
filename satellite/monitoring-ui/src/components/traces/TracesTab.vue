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
      @page="$emit('page', $event)"
      @open="$emit('open', $event)"
      @close-trace="$emit('close-trace')"
    />
  </section>
</template>

<script setup lang="ts">
import type { TraceDetail, TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import TracesPanel from '@/components/TracesPanel.vue'

defineProps<{
  traces: TracesResponse | null
  status: LoadStatus
  openTraceId: string | null
  traceDetail: TraceDetail | null
  traceDetailStatus: LoadStatus
}>()

defineEmits<{ page: [number]; open: [string]; 'close-trace': [] }>()
</script>

<style scoped>
.traces-tab {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
</style>
