<template>
  <section class="output-drift" data-testid="output-drift-tab">
    <div class="intro">
      <p class="section-title">Output drift</p>
      <p class="section-subtitle">
        Did the model's outputs shift against the training reference?
      </p>
    </div>

    <StaleWindowNotice
      v-if="outputDrift?.stale"
      :computed-at="outputDrift.computed_at"
      :window="window"
    />

    <AlertBannerList
      v-if="outputDrift?.alerts?.length"
      :banners="outputDrift.alerts"
      inspectable
      @acknowledge="$emit('acknowledge', $event)"
    />

    <StateBlock
      v-if="view !== 'ready'"
      :view="view"
      :skeleton-rows="4"
      empty-title="No output drift results yet"
      empty-detail="The worker has not materialized output drift for this window yet — it needs
        a reference output summary in the profile and at least one window of traffic."
    />

    <template v-else-if="outputDrift">
      <!-- the score and what it was computed over -->
      <div class="card headline" data-testid="output-headline">
        <div class="score">
          <p class="eyebrow">PSI · {{ outputDrift.name || 'output' }}</p>
          <p class="value">{{ psiLabel }}</p>
          <p
            v-if="outputDrift.psi_delta != null"
            class="headline-delta"
            :class="outputDrift.psi_delta > 0 ? 'up' : 'down'"
            data-testid="output-psi-delta"
          >
            {{ outputDrift.psi_delta > 0 ? '↑' : '↓' }}
            {{ Math.abs(outputDrift.psi_delta).toFixed(2) }} vs compared period
          </p>
        </div>
        <SeverityTag :severity="outputDrift.severity" />
        <p class="count">{{ outputDrift.count.toLocaleString() }} predictions in the window</p>
      </div>

      <div class="charts grid">
        <ChartFrame
          class="card"
          title="Reference vs current distribution"
          :eyebrow="outputDrift.name || 'output'"
        >
          <template #default="{ height }">
            <div class="plot" :style="{ minHeight: `${height}px` }">
              <DistributionChart
                v-if="outputDrift.distribution"
                :distribution="outputDrift.distribution"
                :height="height"
              />
              <p v-else class="chart-empty">
                No distribution in this window yet — it appears with the next window the
                worker closes.
              </p>
            </div>
          </template>
        </ChartFrame>

        <ChartFrame class="card" title="PSI over time" :eyebrow="outputDrift.name || 'output'">
          <template #default="{ height }">
            <div class="plot" :style="{ minHeight: `${height}px` }">
              <SeriesChart
                v-if="outputDrift.psi_over_time"
                :series="outputDrift.psi_over_time"
                color="var(--luml-chart-6)"
                :height="height"
              />
              <p v-else class="chart-empty">
                One window is a reading, not a trend — the chart appears once the worker has
                materialized a second window.
              </p>
            </div>
          </template>
        </ChartFrame>
      </div>

      <ChartFrame
        v-if="outputDrift.trend.length"
        class="card"
        title="Prediction trend"
        subtitle="median inside its p05–p95 band, mean alongside"
        :eyebrow="outputDrift.name || 'output'"
      >
        <template #default="{ height }">
          <PredictionTrendChart :trend="outputDrift.trend" :height="height" />
        </template>
      </ChartFrame>

      <!-- classification with confidence: the early warning — certainty sags before
           the answers themselves go wrong -->
      <template v-if="outputDrift.confidence">
        <div class="card headline" data-testid="confidence-stats">
          <div class="score">
            <p class="eyebrow">Confidence PSI</p>
            <p class="value">{{ score(outputDrift.confidence.psi) }}</p>
          </div>
          <div class="score">
            <p class="eyebrow">Mean confidence</p>
            <p class="value">{{ rate(outputDrift.confidence.mean) }}</p>
          </div>
          <p class="count">
            {{ rate(outputDrift.confidence.low_confidence_rate) }} of predictions below the
            training q05 ({{ rate(outputDrift.confidence.low_confidence_threshold) }})
          </p>
        </div>

        <div class="charts grid">
          <ChartFrame
            v-if="outputDrift.confidence.distribution"
            class="card"
            title="Confidence distribution"
            subtitle="how sure the model is, live vs training"
            eyebrow="Confidence"
          >
            <template #default="{ height }">
              <DistributionChart
                :distribution="outputDrift.confidence.distribution"
                :height="height"
              />
            </template>
          </ChartFrame>

          <ChartFrame
            v-if="outputDrift.confidence.mean_over_time"
            class="card"
            title="Mean confidence over time"
            eyebrow="Confidence"
          >
            <template #default="{ height }">
              <SeriesChart
                :series="outputDrift.confidence.mean_over_time"
                color="var(--luml-chart-4)"
                :height="height"
              />
            </template>
          </ChartFrame>
        </div>
      </template>

      <!-- forecasting: every horizon against its own baseline -->
      <div v-if="outputDrift.horizons.length" class="card" data-testid="horizon-drift">
        <p class="section-title small">Drift by horizon</p>
        <p class="section-subtitle">
          each horizon vs its training baseline — the charts above show the worst one
        </p>
        <ul class="shifts">
          <li v-for="horizon in outputDrift.horizons" :key="horizon.label" class="shift">
            <span class="mono shift-label">{{ horizon.label }}</span>
            <span class="shift-move">
              mean {{ horizon.mean == null ? '—' : horizon.mean.toFixed(2) }}
              · {{ horizon.count.toLocaleString() }} forecasts
            </span>
            <span class="mono shift-delta" :class="psiTone(horizon.psi)">
              PSI {{ horizon.psi.toFixed(2) }}
            </span>
          </li>
        </ul>
      </div>

      <!-- per-class probability drift, from the full vectors the artifact reports -->
      <div
        v-if="outputDrift.probabilities?.per_class?.length"
        class="card"
        data-testid="probability-drift"
      >
        <p class="section-title small">Probability drift by class</p>
        <p class="section-subtitle">
          each class's probability distribution vs its training baseline
        </p>
        <ul class="shifts">
          <li
            v-for="entry in outputDrift.probabilities.per_class"
            :key="entry.label"
            class="shift"
          >
            <span class="mono shift-label">{{ entry.label }}</span>
            <span class="shift-move">
              mean p {{ entry.mean == null ? '—' : entry.mean.toFixed(2) }}
            </span>
            <span class="mono shift-delta" :class="psiTone(entry.psi)">
              PSI {{ entry.psi.toFixed(2) }}
            </span>
          </li>
        </ul>
        <p
          v-if="outputDrift.probabilities.near_threshold"
          class="near-threshold"
          data-testid="near-threshold"
        >
          {{ rate(outputDrift.probabilities.near_threshold.rate) }} of predictions within
          the coin-flip zone of the {{ outputDrift.probabilities.near_threshold.threshold }}
          decision threshold (training: {{
            rate(outputDrift.probabilities.near_threshold.reference_rate)
          }})
        </p>
      </div>

      <!-- classification: which classes moved, built from the labels the model returned -->
      <div v-if="outputDrift.top_changed.length" class="charts grid">
        <div class="card" data-testid="top-changed-classes">
          <p class="section-title small">Top changed classes</p>
          <p class="section-subtitle">share of predictions vs the training reference</p>
          <ul class="shifts">
            <li v-for="shift in outputDrift.top_changed" :key="shift.label" class="shift">
              <span class="mono shift-label">{{ shift.label }}</span>
              <span class="shift-move">
                {{ formatRate(shift.reference) }} → {{ formatRate(shift.current) }}
              </span>
              <span class="mono shift-delta" :class="{ up: shift.delta > 0, down: shift.delta < 0 }">
                {{ shift.delta > 0 ? '+' : '' }}{{ (shift.delta * 100).toFixed(1) }}pp
              </span>
            </li>
          </ul>
        </div>

        <ChartFrame
          v-if="outputDrift.class_share_trend.length"
          class="card"
          title="Class share over time"
          subtitle="live share of each drifted class, per window"
          :eyebrow="outputDrift.name || 'output'"
        >
          <template #default="{ height }">
            <ClassShareChart :series="outputDrift.class_share_trend" :height="height" />
          </template>
        </ChartFrame>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertBanner, OutputDriftResponse } from '@/api/types'
import { Window } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { formatRate } from '@/lib/format'
import StateBlock from '@/components/StateBlock.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import StaleWindowNotice from '@/components/StaleWindowNotice.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'
import ChartFrame from '@/components/ChartFrame.vue'
import SeriesChart from '@/components/SeriesChart.vue'
import DistributionChart from '@/components/feature-drift/DistributionChart.vue'
import PredictionTrendChart from './PredictionTrendChart.vue'
import ClassShareChart from './ClassShareChart.vue'

const props = withDefaults(
  defineProps<{
    outputDrift: OutputDriftResponse | null
    status: LoadStatus
    /** The selected range, so a snapshot from outside it can name what it fell out of. */
    window?: Window
  }>(),
  { window: Window.H24 },
)

defineEmits<{ acknowledge: [AlertBanner] }>()

const view = computed(() => sectionView(props.status, props.outputDrift?.state))

const psiLabel = computed(() => score(props.outputDrift?.psi))

function score(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

function rate(value: number | null | undefined): string {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

/** The PSI bands the alerts use: below 0.1 quiet, to 0.25 warning, above critical. */
function psiTone(psi: number): string {
  if (psi > 0.25) return 'up'
  if (psi >= 0.1) return 'warn'
  return ''
}
</script>

<style scoped>
.output-drift {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.headline-delta {
  margin: 2px 0 0;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.headline-delta.up {
  color: var(--luml-danger-tint-fg);
}
.headline-delta.down {
  color: var(--luml-success-tint-fg);
}
.headline {
  display: flex;
  align-items: center;
  gap: var(--luml-space-5);
  padding: 15px 18px;
}
.score .eyebrow {
  margin: 0 0 2px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.score .value {
  margin: 0;
  font-size: 25px;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--luml-fg-strong);
}
.count {
  margin: 0 0 0 auto;
  font-size: var(--luml-caption-size);
  color: var(--luml-fg-muted);
}
.charts {
  grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr));
}
.shifts {
  margin: var(--luml-space-3) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-2);
}
.shift {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid var(--luml-surface-100);
}
.shift:last-child {
  border-bottom: none;
}
.shift-label {
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.shift-move {
  color: var(--luml-fg-muted);
}
.shift-delta {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}
.shift-delta.up {
  color: var(--luml-danger-tint-fg);
}
.shift-delta.down {
  color: var(--luml-fg-muted);
}
.shift-delta.warn {
  color: var(--luml-warn-tint-fg);
}
.near-threshold {
  margin: var(--luml-space-3) 0 0;
  font-size: var(--luml-caption-size);
  color: var(--luml-fg-muted);
}
.chart-empty {
  margin: 0;
  padding: var(--luml-space-8) var(--luml-space-4);
  text-align: center;
  font-size: var(--luml-caption-size);
  color: var(--luml-fg-muted);
}
</style>
