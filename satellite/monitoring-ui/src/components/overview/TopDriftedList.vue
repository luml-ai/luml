<template>
  <div class="card" data-testid="top-drifted">
    <p class="section-title">Top drifted features</p>
    <p class="section-subtitle">population stability index (PSI)</p>

    <div v-if="features.length" class="rows">
      <div v-for="feature in features" :key="feature.feature" class="row" data-testid="drifted-row">
        <div class="row-head">
          <span class="name mono">{{ feature.feature }}</span>
          <span class="psi"
            >PSI <strong>{{ feature.psi.toFixed(2) }}</strong></span
          >
        </div>
        <div class="track">
          <div
            class="bar"
            :style="{ width: barWidth(feature.psi), background: barColor(feature.severity) }"
          />
        </div>
      </div>
    </div>

    <p v-else class="empty" data-testid="drifted-empty">No feature drift in this window.</p>
  </div>
</template>

<script setup lang="ts">
import { Severity, type DriftedFeature } from '@/api/types'

defineProps<{ features: DriftedFeature[] }>()

// PSI ≥ 0.25 is the conventional "large shift" ceiling; scale the bar against it.
function barWidth(psi: number): string {
  return `${Math.min(100, Math.round((psi / 0.25) * 100))}%`
}

function barColor(severity: Severity): string {
  if (severity === Severity.CRITICAL) return 'var(--luml-danger)'
  if (severity === Severity.WARNING) return 'var(--luml-warn)'
  return 'var(--luml-brand)'
}
</script>

<style scoped>
.rows {
  display: flex;
  flex-direction: column;
  gap: 13px;
  margin-top: var(--luml-space-4);
}
.row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}
.name {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.psi {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.psi strong {
  color: var(--luml-fg-strong);
}
.track {
  height: 8px;
  background: var(--luml-surface-100);
  border-radius: 4px;
  overflow: hidden;
}
.bar {
  height: 100%;
  border-radius: 4px;
}
.empty {
  margin: var(--luml-space-4) 0 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
