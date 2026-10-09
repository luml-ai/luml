<template>
  <div v-if="health && health.state !== 'unavailable'" class="strip" data-testid="worker-health">
    <span class="dot" :class="statusClass" />
    <span class="label">Monitoring worker</span>
    <span class="facts">{{ summary }}</span>
    <span v-if="health.failures.length" class="failures" data-testid="worker-failures">
      {{ failureSummary }}
    </span>
    <span v-else-if="recentIncidents" class="history" data-testid="worker-incidents">
      {{ recentIncidents }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WorkerHealthResponse } from '@/api/types'
import { formatTimestamp } from '@/lib/format'

/** Past this the worker is late enough that the tabs may be showing stale windows. */
const STALE_AFTER_MISSED_TICKS = 3

const props = withDefaults(
  defineProps<{ health?: WorkerHealthResponse | null }>(),
  { health: null },
)

const missedTicks = computed(() => {
  const health = props.health
  if (!health?.last_tick_at || !health.interval_seconds) return 0
  const since = (Date.now() - new Date(health.last_tick_at).getTime()) / 1000
  return since / health.interval_seconds
})

const statusClass = computed(() => {
  const health = props.health
  if (!health?.running) return 'idle'
  if (health.failures.length) return 'failing'
  return missedTicks.value > STALE_AFTER_MISSED_TICKS ? 'late' : 'ok'
})

const summary = computed(() => {
  const health = props.health
  if (!health) return ''
  if (!health.running) return 'has not run yet in this process'

  const parts: string[] = []
  const lastTick = formatTimestamp(health.last_tick_at)
  if (lastTick) parts.push(`last run ${lastTick}`)
  parts.push(`${health.windows_processed} window${health.windows_processed === 1 ? '' : 's'}`)
  if (health.last_lag_seconds != null) {
    parts.push(`${Math.round(health.last_lag_seconds)}s behind the window it closed`)
  }
  return parts.join(' · ')
})

const failureSummary = computed(() => {
  const failures = props.health?.failures ?? []
  if (!failures.length) return ''
  const names = failures.map((failure) => failure.metric).join(', ')
  const ongoing = (props.health?.incidents ?? []).filter((incident) => incident.ongoing)
  const since = formatTimestamp(ongoing[0]?.started_at)
  return since ? `failing: ${names} (since ${since})` : `failing: ${names}`
})

// Past failures are worth showing: restarts wipe the counters.
const recentIncidents = computed(() => {
  const incidents = props.health?.incidents ?? []
  if (!incidents.length) return ''
  const names = [...new Set(incidents.map((incident) => incident.metric))].join(', ')
  const count = incidents.length
  return `${count} recovered failure${count === 1 ? '' : 's'} recently: ${names}`
})
</script>

<style scoped>
.strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--luml-fg-muted);
}
.dot.ok {
  background: var(--luml-success);
}
.dot.late {
  background: var(--luml-warn);
}
.dot.failing {
  background: var(--luml-danger);
}
.label {
  font-weight: 500;
  color: var(--luml-fg);
}
.failures {
  color: var(--luml-danger-tint-fg);
}
.history {
  color: var(--luml-warn-tint-fg);
}
</style>
