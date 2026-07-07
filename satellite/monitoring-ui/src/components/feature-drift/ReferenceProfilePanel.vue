<template>
  <div class="card" data-testid="reference-profile-panel">
    <div class="head">
      <div class="titles">
        <p class="section-title small">Reference profile</p>
        <p class="section-subtitle">{{ baselineLabel }}</p>
      </div>
    </div>

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="3"
      empty-title="No reference profile loaded"
      empty-detail="A training baseline has not been generated for this deployment yet."
    />

    <template v-else-if="feature">
      <div class="feature-head">
        <span class="mono name">{{ feature.feature }}</span>
        <span class="kind">{{ feature.kind }}</span>
      </div>

      <div class="stats">
        <p class="block-title">Summary statistics</p>
        <div class="stat-grid">
          <div v-for="stat in summaryStats" :key="stat.key" class="stat">
            <span class="eyebrow">{{ stat.key }}</span>
            <span class="stat-value mono">{{ stat.value }}</span>
          </div>
        </div>
      </div>

      <div
        v-if="feature.kind === 'categorical'"
        class="categories"
        data-testid="reference-categories"
      >
        <p class="block-title">Reference category probabilities</p>
        <div v-for="cat in categories" :key="cat.name" class="cat-row">
          <span class="cat-name mono">{{ cat.name }}</span>
          <div class="cat-track"><div class="cat-bar" :style="{ width: cat.width }" /></div>
          <span class="cat-prob">{{ cat.prob }}</span>
        </div>
      </div>

      <div v-else class="edges" data-testid="reference-edges">
        <p class="block-title">Histogram bin edges</p>
        <p class="edge-values mono">{{ binEdgesLabel }}</p>
      </div>

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

const baselineLabel = computed(() =>
  props.profile?.baseline_label
    ? `Computed at training · ${props.profile.baseline_label}`
    : 'Training-time baseline distributions',
)

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
.head {
  margin-bottom: var(--luml-space-4);
}
.section-title.small {
  font-size: var(--luml-text-base);
}
.feature-head {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
  margin-bottom: var(--luml-space-4);
}
.feature-head .name {
  font-size: 14px;
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.kind {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--luml-fg-muted);
  padding: 2px 8px;
  border-radius: var(--luml-radius-pill);
  background: var(--luml-surface-100);
}
.block-title {
  margin: 0 0 var(--luml-space-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.stats,
.categories,
.edges {
  margin-top: var(--luml-space-4);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: var(--luml-space-3);
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-value {
  font-size: 14px;
  color: var(--luml-fg-strong);
}
.cat-row {
  display: grid;
  grid-template-columns: 120px 1fr auto;
  align-items: center;
  gap: var(--luml-space-3);
  margin-bottom: 6px;
}
.cat-name {
  font-size: 13px;
  color: var(--luml-fg);
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
.cat-prob {
  font-size: 12px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.edge-values {
  margin: 0;
  font-size: 12px;
  color: var(--luml-fg-muted);
  line-height: 1.7;
}
.note {
  margin: var(--luml-space-4) 0 0;
  font-size: 12px;
  color: var(--luml-fg-muted);
  line-height: 1.5;
}
.prompt {
  text-align: center;
  padding: var(--luml-space-6) var(--luml-space-4);
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
