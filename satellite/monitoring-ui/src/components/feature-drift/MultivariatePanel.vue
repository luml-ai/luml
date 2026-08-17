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
      <!-- chart left, the measures that explain it right — as in the design -->
      <div class="body">
        <PcaScatter
          :reference="panel.reference_projection"
          :current="panel.current_projection"
          :reference-ellipse="panel.reference_ellipse ?? []"
          :current-ellipse="panel.current_ellipse ?? []"
        />

        <div class="measures" data-testid="pca-measures">
          <p class="measures-title">How drift is measured</p>

          <div class="measure" data-testid="pca-shift">
            <div class="measure-head">
              <span class="measure-name">{{ shiftMetricLabel }}</span>
              <span class="measure-value">{{ shiftLabel }}</span>
            </div>
            <p class="measure-sub">distance between population centroids</p>
          </div>

          <div class="measure" data-testid="pca-spread">
            <div class="measure-head">
              <span class="measure-name">Spread vs training</span>
              <span class="measure-value">{{ spreadLabel }}</span>
            </div>
            <p class="measure-sub">generalized variance per component</p>
          </div>

          <div class="measure" data-testid="pca-outliers">
            <div class="measure-head">
              <span class="measure-name">Outlier rate</span>
              <span class="measure-value">{{ outlierLabel }}</span>
            </div>
            <p class="measure-sub">rows past the reference 99th percentile</p>
          </div>

          <div class="measure" data-testid="pca-psi">
            <div class="measure-head">
              <span class="measure-name">Per-feature PSI</span>
              <span class="measure-value">{{ psiSummary }}</span>
            </div>
            <p class="measure-sub">log-bins vs training reference probabilities</p>
          </div>

          <div class="measure" data-testid="pca-variance">
            <div class="measure-head">
              <span class="measure-name">Explained variance</span>
              <span class="measure-value">{{ varianceLabel }}</span>
            </div>
            <p class="measure-sub">
              {{ panel.explained_variance.length }} components retained at training
            </p>
          </div>
        </div>
      </div>

      <p class="footnote">
        Each logged batch is scaled and projected with the PCA basis stored at training, then
        compared to the reference Gaussian: the ellipses are the 95% contours of the two
        distributions, the dots are the logged rows themselves. Per-feature distributions use
        the histogram bins computed during training.
      </p>
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

// The unit belongs to the metric: sigmas for a threshold-based measure, nothing for a
// Mahalanobis distance, which is already expressed in standard deviations of its own space.
const spreadLabel = computed(() =>
  props.panel.dispersion_ratio != null ? `${props.panel.dispersion_ratio.toFixed(2)}×` : '—',
)

const outlierLabel = computed(() =>
  props.panel.outlier_rate != null ? `${(props.panel.outlier_rate * 100).toFixed(1)}%` : '—',
)

const shiftLabel = computed(() => {
  const value = props.panel.shift_value
  if (value == null) return '—'
  const unit = props.panel.shift_unit ?? 'σ'
  return unit ? `${value.toFixed(2)} ${unit}` : value.toFixed(2)
})

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
.body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 268px;
  gap: var(--luml-space-5);
  align-items: start;
}
@media (max-width: 900px) {
  .body {
    grid-template-columns: 1fr;
  }
}
.measures {
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  padding: 14px 16px;
}
.measures-title {
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--luml-fg-muted);
}
.measure + .measure {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--luml-border);
}
.measure-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--luml-space-3);
}
.measure-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg);
}
.measure-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--luml-fg-strong);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.footnote {
  margin: var(--luml-space-4) 0 0;
  padding-top: var(--luml-space-4);
  border-top: 1px solid var(--luml-border);
  font-size: 12px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
.measure-sub {
  margin: 3px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: var(--luml-fg-muted);
}
.empty {
  margin: var(--luml-space-2) 0 0;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
