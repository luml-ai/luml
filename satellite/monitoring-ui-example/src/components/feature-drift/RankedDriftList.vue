<template>
  <div class="card ranked" data-testid="ranked-drift">
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
        <span class="psi-cell">
          <span class="psi">PSI {{ feature.psi.toFixed(2) }}</span>
          <span
            v-if="feature.psi_delta != null"
            class="psi-delta"
            :class="feature.psi_delta > 0 ? 'up' : 'down'"
            data-testid="psi-delta"
          >
            {{ feature.psi_delta > 0 ? '↑' : '↓' }} {{ Math.abs(feature.psi_delta).toFixed(2) }}
          </span>
        </span>
        <SeverityTag :severity="feature.severity" />
      </button>
    </div>

    <div v-else class="empty" data-testid="ranked-empty">
      <p class="empty-title">No features to rank</p>
      <p class="empty-detail">
        Feature drift needs a reference profile and live traffic in this window. Once the worker
        scores one, every input shows up here ordered by PSI.
      </p>
    </div>
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
  /*
    A model with two dozen inputs would make this list the length of the page and push the
    detail panel below the fold. The list fills whatever height the detail panel next to it
    takes — the two read as one section — and scrolls past that; ten rows is the floor so a
    short panel still shows a useful ranking.
  */
  /*
    flex-basis 0 with min-height 0 is what lets the list take the height the panel next to
    it sets instead of its own content: with basis auto it grew to all two dozen rows and
    made the left card taller than the right one.
  */
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}
.ranked {
  display: flex;
  flex-direction: column;
}
.rows::-webkit-scrollbar {
  width: 6px;
}
.rows::-webkit-scrollbar-thumb {
  background: var(--luml-border);
  border-radius: 3px;
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
.psi-cell {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}
/* Drift growing is bad news, shrinking good — the colors follow the meaning. */
.psi-delta {
  font-size: 10.5px;
  font-variant-numeric: tabular-nums;
}
.psi-delta.up {
  color: var(--luml-danger-tint-fg);
}
.psi-delta.down {
  color: var(--luml-success-tint-fg);
}
.psi {
  font-size: 12px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.empty {
  margin: var(--luml-space-4) 0 0;
  padding: var(--luml-space-5) var(--luml-space-4);
  border: 1px dashed var(--luml-border);
  border-radius: var(--luml-radius-md);
  text-align: center;
}
.empty-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.empty-detail {
  margin: 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
