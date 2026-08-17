<template>
  <section class="alerts-tab" data-testid="alerts-tab">
    <div class="intro">
      <p class="section-title">Alerts</p>
      <p class="section-subtitle">
        What needs attention: every threshold still breached in the selected window.
      </p>
    </div>

    <div class="card">
      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="4"
        empty-title="Nothing is firing"
        empty-detail="No metric is past its threshold in this window."
      />

      <template v-else>
        <div class="summary" data-testid="alerts-summary">
          <span class="count">{{ total }} open</span>
          <span v-if="criticals" class="count critical">{{ criticals }} critical</span>
        </div>

        <div v-for="group in alerts?.groups ?? []" :key="group.group" class="group">
          <p class="group-title">
            {{ groupLabel(group.group) }}
            <span class="group-count">{{ group.alerts.length }}</span>
          </p>
          <div
            v-for="alert in group.alerts"
            :key="alert.metric"
            class="row"
            :class="{ selected: alert.metric === selected?.metric }"
            data-testid="alert-row"
            role="button"
            tabindex="0"
            :aria-label="`Inspect ${alert.metric}`"
            @click="selected = alert"
            @keydown.enter.prevent="selected = alert"
            @keydown.space.prevent="selected = alert"
          >
            <span class="dot" :class="`sev-${alert.severity}`" />
            <span class="subject mono">{{ subject(alert) }}</span>
            <span class="reading mono">{{ alert.value_label }}</span>
            <SeverityTag :severity="alert.severity" />
            <!-- The cell is always here so the columns stay aligned down the list. -->
            <span class="ack-cell">
              <span
                v-if="alert.state === 'acknowledged'"
                class="ack"
                title="Someone has seen this alert; it stays until the metric recovers"
                data-testid="alert-acknowledged-chip"
              >
                <Check :size="11" />
                seen
              </span>
            </span>
            <span class="age">{{ durationLabel(alert.duration_seconds) }}</span>
          </div>
        </div>
      </template>
    </div>

    <DetailDrawer
      :open="selected !== null"
      :feature="selected ? subject(selected) : null"
      :kind="selected?.label ?? null"
      :caption="drawerCaption"
      eyebrow="Alert"
      testid="alert-drawer"
      @close="selected = null"
    >
      <template #status>
        <SeverityTag v-if="selected" :severity="selected.severity" />
      </template>
      <AlertDetailPanel
        v-if="selected"
        :alert="selected"
        @show-feature="showFeature"
        @acknowledge="$emit('acknowledge', $event)"
      />
    </DetailDrawer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AlertBanner, AlertsResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { alertSubject, durationLabel, groupLabel } from '@/lib/alerts'
import StateBlock from '@/components/StateBlock.vue'
import { Check } from 'lucide-vue-next'
import SeverityTag from '@/components/SeverityTag.vue'
import DetailDrawer from '@/components/DetailDrawer.vue'
import AlertDetailPanel from './AlertDetailPanel.vue'

const props = defineProps<{
  alerts: AlertsResponse | null
  status: LoadStatus
}>()

const emit = defineEmits<{ 'show-feature': [AlertBanner]; acknowledge: [AlertBanner] }>()

const view = computed(() => {
  const state = sectionView(props.status, props.alerts?.state)
  // An "ok" section with no groups is the good case, not a missing one.
  return state === 'ready' && !props.alerts?.groups?.length ? 'empty' : state
})

const selected = ref<AlertBanner | null>(null)

const total = computed(() =>
  (props.alerts?.groups ?? []).reduce((sum, group) => sum + group.alerts.length, 0),
)
const criticals = computed(() =>
  (props.alerts?.groups ?? []).reduce(
    (sum, group) => sum + group.alerts.filter((a) => a.severity === 'critical').length,
    0,
  ),
)

function subject(alert: AlertBanner): string {
  return alertSubject(alert)
}

const drawerCaption = computed(() => {
  if (!selected.value) return null
  return `${groupLabel(selected.value.group)} · ${selected.value.state ?? 'open'}`
})

function showFeature(alert: AlertBanner): void {
  emit('show-feature', alert)
  selected.value = null
}

// An alert panel must not outlive the alert: a reload may have resolved it.
watch(
  () => props.alerts,
  (response) => {
    if (!selected.value) return
    const key = selected.value.metric
    const all = (response?.groups ?? []).flatMap((group) => group.alerts)
    selected.value = all.find((alert) => alert.metric === key) ?? null
  },
)
</script>

<style scoped>
.alerts-tab {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.summary {
  display: flex;
  gap: var(--luml-space-3);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--luml-border);
}
.count {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.count.critical {
  color: var(--luml-danger-tint-fg);
}
.group + .group {
  margin-top: var(--luml-space-4);
}
.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 14px 0 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.group-count {
  font-weight: 500;
  color: var(--luml-fg-muted);
}
.row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto auto auto 56px;
  align-items: center;
  gap: var(--luml-space-3);
  padding: 9px 10px;
  border-radius: var(--luml-radius-md);
  cursor: pointer;
}
.row:hover,
.row.selected {
  background: var(--luml-surface-50);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.sev-critical {
  background: var(--luml-danger);
}
.dot.sev-warning {
  background: var(--luml-warn);
}
.dot.sev-ok {
  background: var(--luml-success);
}
.subject {
  font-size: 13px;
  color: var(--luml-fg-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.reading {
  font-size: 13px;
  color: var(--luml-fg);
  font-variant-numeric: tabular-nums;
}
.ack-cell {
  display: inline-flex;
  min-width: 0;
}
.ack {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: var(--luml-radius-pill);
  background: var(--luml-surface-100);
  color: var(--luml-fg-muted);
  font-size: 10.5px;
  font-weight: 500;
}
.age {
  font-size: 12px;
  color: var(--luml-fg-muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
