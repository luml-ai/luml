<template>
  <div class="reference-profile" data-testid="reference-profile-panel">
    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="3"
      empty-title="No reference profile loaded"
      empty-detail="A training baseline has not been generated for this deployment yet."
    />

    <template v-else-if="feature">
      <section class="block">
        <p class="block-title">Summary statistics</p>
        <div class="stat-list">
          <div v-for="stat in summaryStats" :key="stat.key" class="stat-row">
            <span class="stat-key">{{ stat.key }}</span>
            <span class="stat-value mono">{{ stat.value }}</span>
          </div>
        </div>
      </section>

      <section
        v-if="feature.kind === 'categorical'"
        class="block"
        data-testid="reference-categories"
      >
        <p class="block-title">Reference category probabilities</p>
        <div v-for="cat in categories" :key="cat.name" class="cat-row">
          <div class="cat-head">
            <span class="cat-name mono" :title="cat.name">{{ cat.name }}</span>
            <span class="cat-prob mono">{{ cat.prob }}</span>
          </div>
          <div class="cat-track"><div class="cat-bar" :style="{ width: cat.width }" /></div>
        </div>
      </section>

      <section v-else class="block" data-testid="reference-edges">
        <p class="block-title">Histogram bin edges</p>
        <p class="edge-values mono">{{ binEdgesLabel }}</p>
      </section>

      <p class="note">
        This profile is the training baseline. Each logged batch is binned with these edges and
        compared against the reference probabilities to compute the feature's PSI drift score.
      </p>
    </template>

    <p v-else class="prompt" data-testid="reference-profile-prompt">
      Select a feature to see its training-time baseline.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReferenceProfileResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import StateBlock from '@/components/StateBlock.vue'

const props = defineProps<{ profile: ReferenceProfileResponse | null; status: LoadStatus }>()

const view = computed(() => sectionView(props.status, props.profile?.state))

const feature = computed(() => props.profile?.feature ?? null)

const summaryStats = computed(() =>
  Object.entries(feature.value?.summary ?? {}).map(([key, value]) => ({
    key,
    value: formatStat(value),
  })),
)

const categories = computed(() => {
  const entry = feature.value
  if (!entry?.categories) return []
  const probabilities = entry.category_probabilities ?? []
  return entry.categories.map((name, index) => {
    const probability = probabilities[index] ?? 0
    return {
      name,
      prob: `${(probability * 100).toFixed(1)}%`,
      width: `${Math.min(100, Math.round(probability * 100))}%`,
    }
  })
})

const binEdgesLabel = computed(() => {
  const edges = feature.value?.bin_edges
  return edges?.length ? edges.map(formatStat).join('  ·  ') : 'Not available'
})

function formatStat(value: number): string {
  if (!Number.isFinite(value)) return String(value)
  if (Number.isInteger(value)) return value.toLocaleString('en-US')
  const magnitude = Math.abs(value)
  if (magnitude >= 1000 || magnitude < 0.01) return value.toPrecision(3)
  return value.toFixed(2)
}
</script>

<style scoped>
.reference-profile {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.block-title {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--luml-fg-muted);
}
/* summary statistics read as one bordered table, separate from the block below it */
.stat-list {
  border: 1px solid var(--luml-border);
  border-radius: 9px;
  overflow: hidden;
}
.stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--luml-space-4);
  padding: 9px 14px;
}
.stat-row + .stat-row {
  border-top: 1px solid var(--luml-border);
}
.stat-key {
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.stat-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.cat-row + .cat-row {
  margin-top: 11px;
}
.cat-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--luml-space-3);
  margin-bottom: 5px;
}
.cat-name {
  font-size: 12.5px;
  color: var(--luml-fg);
  /* a long category label is cut rather than wrapped, so the bars stay aligned */
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cat-prob {
  flex: 0 0 auto;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--luml-fg-strong);
  font-variant-numeric: tabular-nums;
}
.cat-track {
  height: 8px;
  background: var(--luml-surface-100);
  border-radius: 4px;
  overflow: hidden;
}
.cat-bar {
  height: 100%;
  background: var(--luml-brand);
  border-radius: 4px;
}
.edge-values {
  margin: 0;
  padding: 12px 14px;
  background: var(--luml-surface-100);
  border: 1px solid var(--luml-border);
  border-radius: 9px;
  font-size: 12.5px;
  color: var(--luml-fg);
  line-height: 1.6;
  word-break: break-word;
}
.note {
  margin: 0;
  padding: 13px 15px;
  background: var(--luml-brand-tint);
  border: 1px solid var(--luml-brand-tint-strong);
  border-radius: 9px;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--luml-fg);
}
.prompt {
  margin: 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
  text-align: center;
  padding: var(--luml-space-6) var(--luml-space-4);
}
</style>
