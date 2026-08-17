<template>
  <div class="alert-detail" data-testid="alert-detail">
    <section class="block">
      <p class="block-title">Reading</p>
      <div class="stat-list">
        <div class="stat-row">
          <span class="stat-key">{{ alert.label || 'Current value' }}</span>
          <span class="stat-value mono" :class="`sev-${alert.severity}`">
            {{ alert.value_label || '—' }}
          </span>
        </div>
        <div class="stat-row">
          <span class="stat-key">Threshold</span>
          <span class="stat-value mono">{{ alert.threshold_label || '—' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-key">State</span>
          <span class="stat-value mono" data-testid="alert-state">{{ alert.state ?? 'open' }}</span>
        </div>
      </div>
      <p class="block-note">{{ thresholdNote }}</p>
    </section>

    <section class="block" data-testid="alert-timing">
      <p class="block-title">Since when</p>
      <div class="stat-list">
        <div class="stat-row">
          <span class="stat-key">Firing for</span>
          <span class="stat-value mono">{{ durationLabel(alert.duration_seconds) }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-key">First seen</span>
          <span class="stat-value mono">{{ formatTimestamp(alert.first_seen) ?? '—' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-key">Last confirmed</span>
          <span class="stat-value mono">{{ formatTimestamp(alert.last_seen) ?? '—' }}</span>
        </div>
      </div>
    </section>

    <section class="block" data-testid="alert-history">
      <p class="block-title">Metric over time</p>
      <SeriesChart
        v-if="alert.history"
        :series="alert.history"
        :threshold="alert.threshold ?? undefined"
        :color="chartColor"
      />
      <p v-else class="block-note" data-testid="alert-history-empty">
        The metric has been materialized once in this window — a second one turns this into
        a trend.
      </p>
    </section>

    <button
      v-if="canAcknowledge"
      type="button"
      class="jump acknowledge"
      data-testid="alert-acknowledge"
      @click="$emit('acknowledge', alert)"
    >
      Acknowledge
    </button>
    <p v-else-if="acknowledged" class="acknowledged" data-testid="alert-acknowledged">
      Acknowledged — it stays on the list until the metric comes back under its threshold.
    </p>

    <button
      v-if="alert.feature"
      type="button"
      class="jump"
      data-testid="alert-show-feature"
      @click="$emit('show-feature', alert)"
    >
      Show {{ alert.feature }} in {{ groupLabel(alert.group) }}
    </button>

    <p class="note">{{ explanation }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertBanner } from '@/api/types'
import { formatTimestamp } from '@/lib/format'
import { durationLabel, groupLabel } from '@/lib/alerts'
import SeriesChart from '@/components/SeriesChart.vue'

const EXPLANATIONS: Record<string, string> = {
  runtime: 'Raised from the runtime rollup of the window: request outcomes and latency.',
  data_quality:
    'Raised per feature and per check: the share of values that broke the model contract.',
  feature_drift:
    'Raised per feature: PSI of the live distribution against the training reference.',
  output_drift: 'Raised on the predictions themselves, scored the same way as feature drift.',
  multivariate:
    'Raised on the joint distribution: how far the live cloud sits from the training one.',
}

const props = defineProps<{ alert: AlertBanner }>()
defineEmits<{ 'show-feature': [AlertBanner]; acknowledge: [AlertBanner] }>()

const acknowledged = computed(() => props.alert.state === 'acknowledged')
const canAcknowledge = computed(() => !acknowledged.value)

const chartColor = computed(() => (props.alert.severity === 'critical' ? '#ef4444' : '#f97316'))

const thresholdNote = computed(() =>
  props.alert.threshold_source === 'profile'
    ? 'Threshold comes from the deployment reference profile.'
    : 'Threshold is the built-in default; the profile ships its own rules, which the metrics do not read yet.',
)

const explanation = computed(() => EXPLANATIONS[props.alert.group] ?? '')
</script>

<style scoped>
.block + .block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--luml-border);
}
.block-title {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--luml-fg-muted);
}
.block-note {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
.stat-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.stat-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--luml-space-4);
}
.stat-key {
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.stat-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
  font-variant-numeric: tabular-nums;
}
.stat-value.sev-critical {
  color: var(--luml-danger-tint-fg);
}
.stat-value.sev-warning {
  color: var(--luml-warn-tint-fg);
}
.jump {
  margin-top: 18px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.jump:hover {
  background: var(--luml-bg-hover);
}
.acknowledged {
  margin: 18px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
.note {
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--luml-border);
  font-size: 12px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
</style>
