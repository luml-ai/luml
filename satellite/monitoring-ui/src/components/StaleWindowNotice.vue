<template>
  <div class="stale-notice" data-testid="stale-window-notice" role="status">
    <Clock :size="18" class="icon" />
    <div>
      <span class="title">Showing a window from outside this range</span>
      <span class="detail">
        The worker last computed this section at
        <span class="mono">{{ formattedAt }}</span
        >, which is before the selected {{ windowLabel }} range begins. Nothing was lost —
        the trends beside it are read within the range and go empty, while this snapshot
        keeps the last reading. Widen the range or send fresh traffic to see current numbers.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Clock } from 'lucide-vue-next'
import { Window } from '@/api/types'
import { formatTimestamp } from '@/lib/format'

const props = defineProps<{ computedAt?: string | null; window: Window }>()

const formattedAt = computed(() => formatTimestamp(props.computedAt) ?? 'an earlier window')
const windowLabel = computed(() => props.window)
</script>

<style scoped>
.stale-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--luml-space-3);
  padding: var(--luml-space-4) var(--luml-space-5);
  border: 1px solid var(--luml-warn-tint-bg);
  border-radius: var(--luml-radius-lg);
  background: var(--luml-warn-tint-bg);
  color: var(--luml-warn-tint-fg);
}
.icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.title {
  font-weight: 600;
  font-size: 13.5px;
}
.detail {
  margin-left: 8px;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.mono {
  font-family: var(--luml-font-mono, ui-monospace, monospace);
}
</style>
