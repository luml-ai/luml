<template>
  <div class="model-info">
    <section class="performance card">
      <header class="card-header">
        <h3 class="card-title">Model performance</h3>
        <Info
          width="20"
          height="20"
          class="info-icon"
          v-tooltip.bottom="
            `Total score is the share of variance the forecast explains (R²) on held-out data: higher is better, and around 0% means it is no better than predicting the average. MASE separately shows whether it beats a seasonal-naive baseline.`
          "
        />
      </header>
      <div class="total-score">
        <span class="total-score__value">{{ totalScore }}%</span>
        <span class="total-score__label">Total score</span>
      </div>
      <div class="metric-cards">
        <MetricCard
          v-for="card in metricCards"
          :key="card.title"
          :title="card.title"
          :items="card.items"
        />
      </div>
    </section>

    <div class="side-column">
      <section class="config card" data-testid="forecasting-card-config">
        <h3 class="card-title">Model configuration</h3>
        <dl class="config-summary">
          <div>
            <dt>Frequency</dt>
            <dd>{{ modelConfig.frequency }}</dd>
          </div>
          <div>
            <dt>Seasonal period</dt>
            <dd>{{ seasonalPeriodLabel }}</dd>
          </div>
          <div>
            <dt>Aggregation</dt>
            <dd>{{ aggregationLabel }}</dd>
          </div>
          <div>
            <dt>Minimum history</dt>
            <dd>{{ modelConfig.min_history }} rows</dd>
          </div>
          <div>
            <dt>Known-future columns</dt>
            <dd>{{ knownFutureLabel }}</dd>
          </div>
        </dl>
        <table class="config-table">
          <thead>
            <tr>
              <th>Series</th>
              <th>Order (p, d, q)</th>
              <th>Seasonal (P, D, Q)</th>
              <th>Trend</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(cfg, col) in modelConfig.series" :key="col">
              <td>
                {{ col }}<span v-if="col === modelConfig.target_col" class="tag">target</span>
              </td>
              <td>{{ formatOrder(cfg.order) }}</td>
              <td>{{ formatSeasonal(cfg.seasonal_order) }}</td>
              <td>{{ cfg.trend || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="chart" class="chart card" data-testid="forecasting-card-chart">
        <h3 class="card-title">Forecast</h3>
        <ForecastChart :chart="chart" :target-col="modelConfig.target_col" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Info } from 'lucide-vue-next'
import MetricCard from '@/components/ui/MetricCard.vue'
import ForecastChart from '@/components/express-tasks/forecasting/evaluate/ForecastChart.vue'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { toPercent } from '@/helpers/helpers'
import type {
  ForecastingMetrics,
  ForecastingModelConfig,
  ForecastingChart,
} from '@/lib/data-processing/interfaces'

type Props = {
  metrics: ForecastingMetrics
  modelConfig: ForecastingModelConfig
  chart: ForecastingChart | null
}

const props = defineProps<Props>()

const METRIC_TITLES = [
  'Mean Absolute Error',
  'Root Mean Squared Error',
  'Mean Absolute % Error',
  'R² Score',
]

const totalScore = computed(() => toPercent(props.metrics.SC_SCORE))

// Registry bundles carry eval metrics only, so each card shows a single value.
const metricCards = computed(() => {
  const values = FnnxService.getForecastingMetricsRow(props.metrics)
  return METRIC_TITLES.map((title, index) => ({
    title,
    items: [{ value: values[index] }],
  }))
})

const knownFutureLabel = computed(() =>
  props.modelConfig.known_future_cols.length
    ? props.modelConfig.known_future_cols.join(', ')
    : 'None',
)
const seasonalPeriodLabel = computed(() =>
  props.modelConfig.seasonal_period > 0 ? String(props.modelConfig.seasonal_period) : 'None',
)
const aggregationLabel = computed(() =>
  props.modelConfig.aggregation === 'sum' ? 'Sum' : 'Average',
)

function formatOrder(order: [number, number, number]): string {
  return `(${order.join(', ')})`
}

function formatSeasonal(seasonal: [number, number, number, number]): string {
  const [p, d, q, s] = seasonal
  return s > 0 ? `(${p}, ${d}, ${q})·${s}` : 'None'
}
</script>

<style scoped>
.model-info {
  display: grid;
  grid-template-columns: 374px 1fr;
  gap: 20px;
  align-items: start;
}

.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
  margin-bottom: 16px;
}

.info-icon {
  color: var(--p-icon-muted-color);
}

.total-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin-bottom: 24px;
}

.total-score__value {
  font-size: 40px;
  font-weight: 600;
  line-height: 1;
  color: var(--p-primary-color);
}

.total-score__label {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.metric-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.side-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.config-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
  margin-bottom: 16px;
}

.config-summary dt {
  font-size: 13px;
  color: var(--p-text-muted-color);
}

.config-summary dd {
  font-weight: 500;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.config-table th,
.config-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--p-content-border-color);
  text-align: left;
}

.config-table th {
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.tag {
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
  background-color: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

@media (max-width: 1100px) {
  .model-info {
    grid-template-columns: 1fr;
  }
}
</style>
