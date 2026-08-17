<template>
  <div class="invalid-values" data-testid="invalid-values-panel">
    <section class="block">
      <p class="block-title">Checks in this window</p>
      <div class="stat-list">
        <div v-for="check in checks" :key="check.key" class="stat-row" data-testid="dq-check">
          <span class="stat-key">{{ check.key }}</span>
          <span class="stat-value mono" :class="check.severity">{{ check.value }}</span>
        </div>
      </div>
    </section>

    <template v-if="invalid">
      <section
        v-if="invalid.unseen_category_count"
        class="block"
        data-testid="dq-unseen-categories"
      >
        <p class="block-title">Unseen categories</p>
        <p class="block-note">{{ unseenNote }}</p>
        <div v-for="cat in invalid.unseen_categories" :key="cat.value" class="cat-row">
          <span class="cat-name mono" :title="cat.value">{{ cat.value }}</span>
          <span class="cat-count mono">{{ cat.count }}</span>
        </div>
        <p v-if="hiddenCategories > 0" class="block-note">
          and {{ hiddenCategories }} more distinct value{{ hiddenCategories === 1 ? '' : 's' }}
        </p>
      </section>

      <section v-if="invalid.range_violation_count" class="block" data-testid="dq-out-of-range">
        <p class="block-title">Out of range</p>
        <div class="stat-list">
          <div class="stat-row">
            <span class="stat-key">Reference bounds</span>
            <span class="stat-value mono">{{ referenceBounds }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-key">Observed extremes</span>
            <span class="stat-value mono critical">{{ observedExtremes }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-key">Below minimum</span>
            <span class="stat-value mono" :class="{ critical: invalid.below_min > 0 }">
              {{ invalid.below_min }}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-key">Above maximum</span>
            <span class="stat-value mono" :class="{ critical: invalid.above_max > 0 }">
              {{ invalid.above_max }}
            </span>
          </div>
        </div>
      </section>

      <section v-if="invalid.type_mismatch_count" class="block" data-testid="dq-type-errors">
        <p class="block-title">Type errors</p>
        <div class="stat-list">
          <div v-for="type in observedTypes" :key="type.name" class="stat-row">
            <span class="stat-key mono">{{ type.name }}</span>
            <span class="stat-value mono">{{ type.count }}</span>
          </div>
        </div>
        <p v-if="invalid.type_examples.length" class="block-note">
          e.g. <span class="mono">{{ invalid.type_examples.join(', ') }}</span>
        </p>
      </section>
    </template>

    <p v-else class="clean" data-testid="dq-no-invalid">{{ noEvidenceLabel }}</p>

    <section class="block" data-testid="dq-trends">
      <p class="block-title">Over time</p>
      <p v-if="trendsStatus === 'loading'" class="block-note">Loading history…</p>
      <template v-else-if="trends.length">
        <div v-for="series in trends" :key="series.key" class="trend">
          <p class="trend-name">{{ series.label }}</p>
          <SeriesChart :series="series" :color="trendColor(series.key)" />
        </div>
      </template>
      <p v-else class="block-note" data-testid="dq-trends-empty">
        One window is a reading, not a trend — the chart appears once the worker has
        materialized a second window.
      </p>
    </section>

    <p class="note">{{ contractNote }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DataQualityFeatureRow, Series } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import SeriesChart from '@/components/SeriesChart.vue'
import { formatRate } from '@/lib/format'
import { rateClass } from '@/lib/dataQuality'

const props = withDefaults(
  defineProps<{ row: DataQualityFeatureRow; trends?: Series[]; trendsStatus?: LoadStatus }>(),
  { trends: () => [], trendsStatus: 'idle' },
)

// Each check keeps the colour of the severity it usually raises, so the charts read
// together with the table above them.
const TREND_COLORS: Record<string, string> = {
  missing: '#f97316',
  type_mismatch: '#ef4444',
  range_violation: '#2673fd',
  unseen_category: '#8b5cf6',
}

function trendColor(key: string): string {
  return TREND_COLORS[key] ?? '#2673fd'
}

const invalid = computed(() => props.row.invalid ?? null)
const isCategorical = computed(() => props.row.kind === 'categorical')

/** "2.0% · 3 of 151" — the rate the table shows, plus the counts behind it. */
function share(rate: number | null | undefined, count: number): string {
  const checked = props.row.checked
  const counts = checked != null ? ` · ${count} of ${checked.toLocaleString()}` : ` · ${count}`
  return `${formatRate(rate)}${counts}`
}

const checks = computed(() => {
  const detail = invalid.value
  // Each rate is coloured by its own spec threshold, the way the table colours its columns.
  const rows = [
    {
      key: 'Missing',
      value: share(props.row.missing_rate, detail?.missing_count ?? 0),
      severity: rateClass(props.row.missing_rate, 'missing'),
    },
    {
      key: 'Type errors',
      value: share(props.row.type_error_rate, detail?.type_mismatch_count ?? 0),
      severity: rateClass(props.row.type_error_rate, 'type_mismatch'),
    },
  ]
  if (isCategorical.value) {
    rows.push({
      key: 'Unseen categories',
      value: share(props.row.unseen_category_rate, detail?.unseen_category_count ?? 0),
      severity: rateClass(props.row.unseen_category_rate, 'unseen_category'),
    })
  } else {
    rows.push({
      key: 'Out of range',
      value: share(props.row.range_violation_rate, detail?.range_violation_count ?? 0),
      severity: rateClass(props.row.range_violation_rate, 'range_violation'),
    })
  }
  return rows
})

const unseenNote = computed(() => {
  const detail = invalid.value
  if (!detail) return ''
  const distinct = `${detail.unseen_distinct} distinct value${detail.unseen_distinct === 1 ? '' : 's'}`
  const known = detail.reference_categories
  return known != null
    ? `${distinct} the training reference never saw; it holds ${known} categor${known === 1 ? 'y' : 'ies'}.`
    : `${distinct} the training reference never saw.`
})

// A window materialized before the checks kept their evidence has rates but nothing to
// show behind them — saying "everything matched" there would be a lie.
const noEvidenceLabel = computed(() => {
  const rates = [
    props.row.missing_rate,
    props.row.type_error_rate,
    props.row.range_unseen_rate,
  ]
  return rates.some((rate) => (rate ?? 0) > 0)
    ? 'This window was computed before the per-value breakdown was recorded.'
    : 'Every value in this window matched the model contract.'
})

const hiddenCategories = computed(() => {
  const detail = invalid.value
  if (!detail) return 0
  return Math.max(0, detail.unseen_distinct - detail.unseen_categories.length)
})

function formatBound(value: number | null | undefined): string {
  if (value == null) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

const referenceBounds = computed(() => {
  const detail = invalid.value
  if (!detail) return '—'
  return `${formatBound(detail.reference_min)} … ${formatBound(detail.reference_max)}`
})

const observedExtremes = computed(() => {
  const detail = invalid.value
  if (!detail) return '—'
  return `${formatBound(detail.observed_min)} … ${formatBound(detail.observed_max)}`
})

const observedTypes = computed(() =>
  Object.entries(invalid.value?.observed_types ?? {}).map(([name, count]) => ({ name, count })),
)

const contractNote = computed(() =>
  isCategorical.value
    ? 'Values are checked against the categories recorded in the training reference profile. Categories outside that set are counted as unseen.'
    : 'Values are checked against the min and max recorded in the training reference profile. Anything outside those bounds is counted as out of range.',
)
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
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
.block-title + .block-note {
  margin: -4px 0 10px;
}
.stat-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.stat-row,
.cat-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--luml-space-4);
  min-width: 0;
}
.cat-row + .cat-row {
  margin-top: 7px;
}
.stat-key,
.cat-name {
  font-size: 13px;
  color: var(--luml-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stat-value,
.cat-count {
  flex: 0 0 auto;
  font-size: 13px;
  font-weight: 500;
  color: var(--luml-fg-strong);
  font-variant-numeric: tabular-nums;
}
.warn {
  color: var(--luml-warn-tint-fg);
}
.critical {
  color: var(--luml-danger-tint-fg);
}
.trend + .trend {
  margin-top: 10px;
}
.trend-name {
  margin: 0;
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.clean {
  margin: 18px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--luml-border);
  font-size: 13px;
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
