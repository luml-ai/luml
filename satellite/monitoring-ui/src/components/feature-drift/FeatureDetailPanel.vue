<template>
  <div class="card" data-testid="feature-detail">
    <template v-if="detail">
      <div class="head">
        <div class="titles">
          <p class="section-title small mono">{{ detail.feature }}</p>
          <p class="section-subtitle">
            {{ psiLabel }}
          </p>
        </div>
        <div class="head-meta">
          <span v-if="kindLabel" class="kind" data-testid="feature-kind">{{ kindLabel }}</span>
          <SeverityTag :severity="detail.status" />
          <button
            type="button"
            class="reference"
            data-testid="open-reference-profile"
            @click="$emit('open-reference')"
          >
            Reference profile
          </button>
        </div>
      </div>

      <div class="charts">
        <div class="chart">
          <p class="chart-title">Reference vs current distribution</p>
          <!-- The empty state keeps the chart's own height: a section that changes size
               depending on whether data arrived reads as a broken layout. -->
          <div class="plot">
            <DistributionChart v-if="detail.distribution" :distribution="detail.distribution" />
            <p v-else class="chart-empty">No distribution available for this feature.</p>
          </div>
        </div>
        <div class="chart">
          <p class="chart-title">PSI over time</p>
          <div class="plot">
            <SeriesChart
              v-if="detail.psi_over_time"
              :series="detail.psi_over_time"
              color="#a855f7"
            />
            <p v-else class="chart-empty">
              No PSI history yet — a trend needs a second materialized window.
            </p>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="prompt" data-testid="feature-detail-prompt">
      <p class="prompt-title">{{ emptyTitle }}</p>
      <p class="prompt-detail">{{ emptyDetail }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeatureDriftDetail } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import DistributionChart from './DistributionChart.vue'

const props = defineProps<{
  detail: FeatureDriftDetail | null | undefined
  /** numeric | categorical, from the reference profile; the drift payload only knows it
   * once a distribution has been materialized. */
  kind?: string | null
  /** whether the ranking beside this panel has anything to select at all */
  hasFeatures?: boolean
}>()

defineEmits<{ 'open-reference': [] }>()

const psiLabel = computed(() =>
  props.detail?.psi != null ? `PSI ${props.detail.psi.toFixed(2)}` : 'PSI not available',
)

// With an empty ranking there is nothing to select, so asking the reader to pick a feature
// would send them to a list that cannot answer.
const emptyTitle = computed(() =>
  props.hasFeatures === false ? 'Nothing to inspect yet' : 'No feature selected',
)
const emptyDetail = computed(() =>
  props.hasFeatures === false
    ? 'Feature drift for this window has not been computed, so there is no distribution to compare.'
    : 'Pick a feature from the ranking to see its reference-vs-current distribution and PSI trend.',
)

const kindLabel = computed(() => {
  const kind = props.kind ?? props.detail?.distribution?.kind ?? null
  if (!kind) return null
  return kind === 'numeric' ? 'Numerical' : 'Categorical'
})
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--luml-space-4);
  margin-bottom: var(--luml-space-4);
}
.section-title.small {
  font-size: var(--luml-text-base);
}
.head-meta {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
  flex-wrap: wrap;
  justify-content: flex-end;
}
.kind {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--luml-fg-muted);
  background: var(--luml-surface-100);
  border-radius: 4px;
  padding: 3px 7px;
}
.reference {
  font-size: 12px;
  font-weight: 500;
  color: var(--luml-brand);
  background: none;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  padding: 4px 10px;
  cursor: pointer;
}
.reference:hover {
  background: var(--luml-bg-hover);
}
/* stacked, not side by side: the PSI trend reads as the history of the distribution above it,
   and both get the full width of the panel */
.charts {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-5);
}
.chart-title {
  margin: 0 0 var(--luml-space-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
/* Distribution chart is 230px tall, the PSI series 180px; the box keeps that space
   whether or not the data arrived. Column flow on purpose: a row would shrink the chart
   to its content width and squash it. */
.plot {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 230px;
}
.chart + .chart .plot {
  min-height: 180px;
}
.chart-empty {
  margin: 0;
  font-size: 13px;
  text-align: center;
  color: var(--luml-fg-muted);
}
.prompt {
  text-align: center;
  padding: var(--luml-space-6) var(--luml-space-4);
}
.prompt-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.prompt-detail {
  margin: 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
