<template>
  <div class="setup-bar">
    <div class="headings">
      <h1 class="main-title">Configure your forecast</h1>
      <p class="sub-title">
        Assign the date, target and auxiliary roles from the table column menus below. Model orders
        and seasonality are detected automatically.
      </p>
    </div>

    <div class="controls">
      <label class="field">
        <span class="label">Frequency</span>
        <d-select
          ref="frequencySelect"
          v-model="frequency"
          :options="FREQUENCIES"
          option-label="label"
          option-value="value"
          fluid
        />
      </label>

      <label class="field">
        <span class="label">Aggregation</span>
        <d-select
          ref="aggregationSelect"
          v-model="aggregation"
          :options="AGGREGATIONS"
          option-label="label"
          option-value="value"
          fluid
        />
        <small class="hint">
          Combines rows that fall in the same {{ frequency }} — sum for totals (sales, counts),
          average for levels (price, rate).
        </small>
      </label>

      <label v-if="!hasKnownFuture" class="field">
        <span class="label">Training preview up to (optional)</span>
        <date-picker
          ref="previewDate"
          v-model="previewEndDate"
          :min-date="lastHistoricalDate ?? undefined"
          date-format="yy-mm-dd"
          placeholder="Select end date"
          show-icon
          show-button-bar
          fluid
        />
      </label>
    </div>

    <small v-if="dateNotParseable" class="error" data-testid="error-date-parseable">
      The date column doesn't contain recognizable dates — pick another one from its column menu.
    </small>
    <small v-if="targetNotNumeric" class="error" data-testid="error-target-numeric">
      The target column doesn't contain numeric values — pick another one from its column menu.
    </small>
    <small v-if="previewDateInvalid" class="error" data-testid="error-preview-date">
      The preview end date must be after the last historical date.
    </small>
    <small v-if="hasKnownFuture" class="hint" data-testid="preview-hint">
      Training preview is unavailable with known-future columns — their future values don't exist
      yet. Use the Model Evaluation step to re-forecast once you can supply them.
    </small>
  </div>
</template>

<script setup lang="ts">
import DatePicker from 'primevue/datepicker'
import type { ForecastingAggregation, ForecastingFrequency } from '@/lib/data-processing/interfaces'

type Props = {
  hasKnownFuture: boolean
  lastHistoricalDate: Date | null
  dateNotParseable: boolean
  targetNotNumeric: boolean
  previewDateInvalid: boolean
}

defineProps<Props>()
const frequency = defineModel<ForecastingFrequency>('frequency', { required: true })
const aggregation = defineModel<ForecastingAggregation>('aggregation', { required: true })
const previewEndDate = defineModel<Date | null>('previewEndDate', { required: true })

const FREQUENCIES: { label: string; value: ForecastingFrequency }[] = [
  { label: 'Day', value: 'day' },
  { label: 'Week', value: 'week' },
  { label: 'Month', value: 'month' },
  { label: 'Quarter', value: 'quarter' },
  { label: 'Year', value: 'year' },
]

const AGGREGATIONS: { label: string; value: ForecastingAggregation }[] = [
  { label: 'Average', value: 'mean' },
  { label: 'Sum', value: 'sum' },
]
</script>

<style scoped>
.setup-bar {
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.headings {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.main-title {
  font-size: 20px;
}

.sub-title {
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.controls {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 280px));
  gap: 16px;
  align-items: start;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-weight: 500;
  font-size: 14px;
}

.error {
  color: var(--p-message-error-color, var(--p-red-500));
  font-size: 13px;
}

.hint {
  color: var(--p-text-muted-color);
  font-size: 13px;
}

@media (max-width: 900px) {
  .controls {
    grid-template-columns: repeat(2, minmax(0, 280px));
  }
}

@media (max-width: 768px) {
  .controls {
    grid-template-columns: 1fr;
  }
}
</style>
