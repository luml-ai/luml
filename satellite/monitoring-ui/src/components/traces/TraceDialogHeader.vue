<template>
  <div class="header">
    <MEllipsis :id="titleId" class="title" :text="title" />
    <div v-if="eventId" class="badge">
      <span class="badge-text">{{ shortEventId }}</span>
      <MCopyButton :text="eventId" label="request ID" />
    </div>
    <div v-if="trace" class="request" data-testid="trace-request-facts">
      <Tag :value="getOutcomeLabel(trace.status)" :severity="getTraceStatusSeverity(trace)" />
      <span class="fact">HTTP {{ trace.status_code }}</span>
      <span class="fact">{{ formatMs(trace.latency_ms) }}</span>
      <span class="fact muted">{{ formatTimestamp(trace.ts) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { TraceDetail } from '@/api/monitoring/interfaces'
import { getTraceStatusSeverity, shortenId } from '@/utils/traces'
import { getOutcomeLabel } from '@/utils/runtime'
import { formatMs, formatTimestamp } from '@/utils/format'
import MCopyButton from '@/components/MCopyButton.vue'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  titleId?: string
  title: string
  eventId: string | null
  trace?: TraceDetail | null
}

const props = withDefaults(defineProps<Props>(), {
  trace: null,
})

const shortEventId = computed(() => (props.eventId ? shortenId(props.eventId) : ''))
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.badge {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 8px;
  border-radius: var(--p-tag-border-radius);
  background: var(--p-content-background);
  font-size: 12px;
  color: var(--p-text-color);
}

.badge-text {
  white-space: nowrap;
}

.request {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--p-text-color);
  white-space: nowrap;
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
