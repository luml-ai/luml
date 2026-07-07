<template>
  <div class="card" data-testid="multivariate-panel">
    <div class="head">
      <div class="titles">
        <p class="section-title small">Multivariate drift (PCA)</p>
        <p class="section-subtitle">
          PC1 × PC2 projection · reference vs logged, from the training PCA basis.
        </p>
      </div>
      <SeverityTag v-if="isReady" :severity="panel.status" />
    </div>

    <template v-if="isReady">
      <PcaScatter :reference="panel.reference_projection" :current="panel.current_projection" />

      <div class="measures">
        <div class="measure" data-testid="pca-shift">
          <span class="eyebrow">{{ shiftMetricLabel }}</span>
          <span class="measure-value">{{ shiftLabel }}</span>
        </div>
        <div class="measure" data-testid="pca-psi">
          <span class="eyebrow">Per-feature PSI</span>
          <span class="measure-value">{{ psiSummary }}</span>
          <span class="measure-sub">features ≥ 0.2 vs training</span>
        </div>
        <div class="measure" data-testid="pca-variance">
          <span class="eyebrow">Explained variance</span>
          <span class="measure-value">{{ varianceLabel }}</span>
          <span class="measure-sub">{{ panel.explained_variance.length }} components retained</span>
        </div>
      </div>
    </template>

    <p v-else class="empty" data-testid="pca-empty">
      Multivariate drift has not been computed for this window yet.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SectionState, type MultivariatePanel as MultivariatePanelData } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import PcaScatter from './PcaScatter.vue'

// PSI ≥ 0.2 is the conventional "moderate shift" line the design summarizes multivariately.
const PSI_ATTENTION = 0.2

const props = defineProps<{ panel: MultivariatePanelData }>()

const isReady = computed(() => props.panel.state === SectionState.OK)

const shiftMetricLabel = computed(() =>
  props.panel.shift_metric ? props.panel.shift_metric.replace(/_/g, ' ') : 'Shift distance',
)

const shiftLabel = computed(() =>
  props.panel.shift_value != null ? `${props.panel.shift_value.toFixed(2)} σ` : '—',
)

const psiSummary = computed(() => {
  const total = props.panel.feature_psi.length
  const above = props.panel.feature_psi.filter((f) => f.psi >= PSI_ATTENTION).length
  return `${above} / ${total}`
})

const varianceLabel = computed(() => {
  const variance = props.panel.explained_variance
  if (!variance.length) return '—'
  const total = variance.reduce((sum, value) => sum + value, 0)
  return `${(total * 100).toFixed(1)}%`
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
.measures {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--luml-space-4);
  margin-top: var(--luml-space-5);
}
.measure {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 12px 14px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
}
.measure-value {
  font-size: 20px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.measure-sub {
  font-size: 11px;
  color: var(--luml-fg-muted);
}
.empty {
  margin: var(--luml-space-2) 0 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
