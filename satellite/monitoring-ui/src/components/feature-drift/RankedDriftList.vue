<template>
  <div class="card" data-testid="ranked-drift">
    <p class="section-title small">Ranked feature drift</p>
    <p class="section-subtitle">
      How far each live input has moved from the training reference. Select a feature for detail.
    </p>

    <div v-if="features.length" class="rows" role="listbox">
      <button
        v-for="feature in features"
        :key="feature.feature"
        type="button"
        class="row"
        :class="{ selected: feature.feature === selected }"
        :aria-selected="feature.feature === selected"
        data-testid="ranked-row"
        @click="$emit('select', feature.feature)"
      >
        <span class="name mono">{{ feature.feature }}</span>
        <span class="psi">PSI {{ feature.psi.toFixed(2) }}</span>
        <SeverityTag :severity="feature.severity" />
      </button>
    </div>

    <p v-else class="empty" data-testid="ranked-empty">
      No feature drift computed for this window.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { DriftedFeature } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'

defineProps<{ features: DriftedFeature[]; selected: string | null }>()
defineEmits<{ select: [string] }>()
</script>

<style scoped>
.section-title.small {
  font-size: var(--luml-text-base);
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: var(--luml-space-4);
}
.row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: var(--luml-space-4);
  padding: 9px 12px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.row:hover {
  background: var(--luml-bg-hover);
}
.row.selected {
  border-color: var(--luml-brand);
  background: var(--luml-brand-tint);
}
.name {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.psi {
  font-size: 12px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.empty {
  margin: var(--luml-space-4) 0 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
