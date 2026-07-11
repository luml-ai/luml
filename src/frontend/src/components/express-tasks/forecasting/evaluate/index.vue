<template>
  <div class="evaluate" data-testid="forecasting-evaluate">
    <header class="header">
      <h1 class="title">Model Evaluation Dashboard</h1>
      <div class="buttons">
        <SplitButton
          label="export"
          severity="secondary"
          data-testid="export-model"
          :model="EXPORT_ITEMS"
          @click="onDownloadClick"
        />
        <d-button data-testid="exit" @click="finishConfirm">
          <span>exit</span>
          <log-out width="14" height="14" />
        </d-button>
      </div>
    </header>

    <div class="body">
      <ModelTabularPerformance
        :total-score="totalScore"
        :test-metrics="testMetrics"
        :training-metrics="trainingMetrics"
        :tag="FNNX_PRODUCER_TAGS_MANIFEST_ENUM.forecasting_v1"
        class="performance"
      ></ModelTabularPerformance>

      <section class="config card" data-testid="model-config">
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
            <dd data-testid="aggregation">{{ aggregationLabel }}</dd>
          </div>
          <div>
            <dt>Minimum history</dt>
            <dd data-testid="min-history">{{ modelConfig.min_history }} rows</dd>
          </div>
          <div>
            <dt>Known-future columns</dt>
            <dd data-testid="known-future">{{ knownFutureLabel }}</dd>
          </div>
        </dl>
        <p class="config-note">
          Predictions require at least {{ modelConfig.min_history }} rows of recent history<span
            v-if="hasKnownFuture"
          >
            plus future values for {{ knownFutureLabel }}</span
          >.
        </p>
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

      <section class="chart card">
        <h3 class="card-title">Forecast</h3>
        <forecast-chart
          :chart="chart"
          :target-col="modelConfig.target_col"
          :prediction="overlay"
          :supplied="supplied"
        />
      </section>

      <section class="reforecast card">
        <h3 class="card-title">Re-forecast</h3>
        <p class="reforecast-sub">
          Extend the forecast to a future date using the training series as history — no retraining.
        </p>
        <div class="controls">
          <label class="field">
            <span class="label">Forecast up to</span>
            <date-picker
              v-model="endDate"
              :min-date="lastHistoryDate ?? undefined"
              date-format="yy-mm-dd"
              placeholder="Select end date"
              show-icon
              fluid
              data-testid="reforecast-date"
            />
          </label>
        </div>

        <future-values-editor
          v-if="hasKnownFuture && forecastDates.length"
          :dates="forecastDates"
          :columns="knownFutureCols"
          :date-col="modelConfig.date_col"
          :frequency="modelConfig.frequency"
          @change="onFutureChange"
        />

        <div class="reforecast-actions">
          <d-button
            :disabled="!canForecast || isForecasting"
            data-testid="run-forecast"
            @click="runForecast"
          >
            Forecast
          </d-button>
          <d-button
            severity="secondary"
            :disabled="!displayRecords.length"
            data-testid="download-predictions"
            @click="downloadPredictions"
          >
            Download predictions
          </d-button>
        </div>
        <p v-if="isForecasting" class="forecast-status" data-testid="forecast-status">
          generating forecast…
        </p>
      </section>
    </div>
  </div>
  <ModelUpload
    v-if="modelBlob && !!organizationStore.currentOrganization"
    v-model:visible="modelUploadVisible"
    :model-blob="modelBlob"
    :current-task="Tasks.FORECASTING"
  ></ModelUpload>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DatePicker from 'primevue/datepicker'
import { SplitButton } from 'primevue'
import { LogOut } from 'lucide-vue-next'
import ForecastChart from './ForecastChart.vue'
import FutureValuesEditor from './FutureValuesEditor.vue'
import ModelUpload from '@/components/model-upload/ModelUpload.vue'
import ModelTabularPerformance from '@/components/model/ModelTabularPerformance.vue'
import { useOrganizationStore } from '@/stores/organization'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import { downloadFileFromBlob } from '@/helpers/helpers'
import { normalizeForecastRecords } from '@/lib/data-processing/forecasting'
import { Tasks } from '@/lib/data-processing/interfaces'
import {
  generateForecastDates,
  lastDate,
  periodsBetween,
} from '@/lib/data-processing/forecasting-setup'
import type {
  ForecastPoint,
  ForecastPredictedRecord,
  ForecastingChart,
  ForecastingModelConfig,
  ForecastingPredictRequest,
  ForecastingPredictSuccess,
  ForecastingRecord,
} from '@/lib/data-processing/interfaces'

type Props = {
  totalScore: number
  testMetrics: string[]
  trainingMetrics: string[]
  modelConfig: ForecastingModelConfig
  chart: ForecastingChart
  history: ForecastingRecord[]
  modelId: string
  modelBlob: Blob | null
  predict: (request: ForecastingPredictRequest) => Promise<ForecastingPredictSuccess | undefined>
  downloadModel: () => void
}

const props = defineProps<Props>()
const router = useRouter()
const organizationStore = useOrganizationStore()

const modelUploadVisible = ref(false)

const EXPORT_ITEMS = [
  {
    label: 'Upload to Registry',
    command: () => {
      modelUploadVisible.value = true
    },
    disabled: () => !organizationStore.currentOrganization,
  },
  {
    label: 'Download model',
    command: () => {
      onDownloadClick()
    },
  },
]

const endDate = ref<Date | null>(null)
const isForecasting = ref(false)
const rawForecast = ref<ForecastPredictedRecord[]>([])
const rawFuture = ref<ForecastingRecord[]>([])
const futureState = ref<{ complete: boolean; future: ForecastingRecord[] }>({
  complete: false,
  future: [],
})

const knownFutureCols = computed(() => props.modelConfig.known_future_cols)
const hasKnownFuture = computed(() => knownFutureCols.value.length > 0)
const knownFutureLabel = computed(() =>
  knownFutureCols.value.length ? knownFutureCols.value.join(', ') : 'None',
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

const lastHistoryDate = computed(() => lastDate(props.history, props.modelConfig.date_col))
const horizon = computed(() =>
  lastHistoryDate.value && endDate.value
    ? periodsBetween(lastHistoryDate.value, endDate.value, props.modelConfig.frequency)
    : 0,
)
const forecastDates = computed(() =>
  lastHistoryDate.value && horizon.value > 0
    ? generateForecastDates(lastHistoryDate.value, horizon.value, props.modelConfig.frequency)
    : [],
)
const canForecast = computed(
  () => horizon.value > 0 && (!hasKnownFuture.value || futureState.value.complete),
)

const displayRecords = computed<ForecastPredictedRecord[]>(() => rawForecast.value)

const overlay = computed(() =>
  displayRecords.value.length
    ? normalizeForecastRecords(
        displayRecords.value,
        props.modelConfig.date_col,
        props.modelConfig.target_col,
      )
    : null,
)

const supplied = computed<Record<string, ForecastPoint[]> | null>(() => {
  if (!hasKnownFuture.value || !displayRecords.value.length) return null
  const dateCol = props.modelConfig.date_col
  const byDate = new Map(rawFuture.value.map((record) => [String(record[dateCol]), record]))
  const result: Record<string, ForecastPoint[]> = {}
  for (const col of knownFutureCols.value) {
    result[col] = displayRecords.value
      .map((record) => {
        const date = String(record[dateCol])
        return { date, value: Number(byDate.get(date)?.[col]) }
      })
      .filter((point) => Number.isFinite(point.value))
  }
  return result
})

// Editing a future value invalidates any prior forecast the same way a changed
// horizon does — otherwise the chart overlay and download keep the old inputs.
function onFutureChange(state: { complete: boolean; future: ForecastingRecord[] }): void {
  futureState.value = state
  rawForecast.value = []
  rawFuture.value = []
}

async function runForecast(): Promise<void> {
  if (!canForecast.value || isForecasting.value) return
  const request: ForecastingPredictRequest = {
    model_id: props.modelId,
    history: props.history,
    horizon: horizon.value,
  }
  if (hasKnownFuture.value) request.future = futureState.value.future
  isForecasting.value = true
  try {
    const result = await props.predict(request)
    if (!result) return
    rawForecast.value = result.forecast
    rawFuture.value = hasKnownFuture.value ? futureState.value.future : []
  } finally {
    isForecasting.value = false
  }
}

function downloadPredictions(): void {
  const records = displayRecords.value
  if (!records.length) return
  const blob = new Blob([recordsToCsv(records)], { type: 'text/csv;charset=utf-8;' })
  downloadFileFromBlob(blob, `forecast_predictions_${Date.now()}.csv`)
}

function recordsToCsv(records: ForecastPredictedRecord[]): string {
  const headers = Object.keys(records[0])
  const rows = records.map((record) => headers.map((header) => record[header]).join(','))
  return [headers.join(','), ...rows].join('\n')
}

function onDownloadClick(): void {
  props.downloadModel()
  AnalyticsService.track(AnalyticsTrackKeysEnum.download, { task: 'forecasting' })
}

function finishConfirm(): void {
  AnalyticsService.track(AnalyticsTrackKeysEnum.finish, { task: 'forecasting' })
  router.push({ name: 'home' })
}

// A changed horizon invalidates any prior forecast.
watch(endDate, () => {
  rawForecast.value = []
  rawFuture.value = []
})
</script>

<style scoped>
.evaluate {
  padding-top: 32px;
  padding-bottom: 32px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.title {
  font-size: 24px;
}

.buttons {
  display: flex;
  gap: 8px;
}

.body {
  display: grid;
  grid-template-columns: 374px 1fr;
  gap: 24px;
  align-items: start;
}

.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-title {
  font-size: 20px;
  margin-bottom: 16px;
}

.performance {
  grid-row: span 2;
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

.config-note {
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--p-text-muted-color);
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

.tag,
.config-table .tag {
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
  background-color: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

.chart {
  grid-column: 2;
}

.reforecast {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.reforecast-sub {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.controls {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-weight: 500;
  font-size: 14px;
}

.reforecast-actions {
  display: flex;
  gap: 12px;
}

.forecast-status {
  font-size: 13px;
  color: var(--p-text-muted-color);
}

@media (max-width: 1200px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
  }

  .body {
    grid-template-columns: 1fr;
  }

  .chart,
  .reforecast {
    grid-column: auto;
  }

  .performance {
    grid-row: auto;
  }
}
</style>
