<template>
  <div class="setup">
    <div class="headings">
      <h1 class="main-title">Configure your forecast</h1>
      <p class="sub-title">
        Assign column roles and the observation frequency. The model orders and seasonality are
        detected automatically.
      </p>
    </div>

    <div class="grid">
      <label class="field">
        <span class="label">Date column</span>
        <d-select
          ref="dateSelect"
          v-model="dateCol"
          :options="columns"
          placeholder="Select date column"
          fluid
        />
        <small v-if="dateNotParseable" class="error" data-testid="error-date-parseable">
          The selected date column doesn't contain recognizable dates.
        </small>
      </label>

      <label class="field">
        <span class="label">Target column</span>
        <d-select
          ref="targetSelect"
          v-model="targetCol"
          :options="columns"
          placeholder="Select target column"
          fluid
        />
        <small v-if="sameDateTarget" class="error" data-testid="error-same-columns">
          The date and target must be different columns.
        </small>
      </label>

      <label class="field">
        <span class="label">Auxiliary columns (optional)</span>
        <multi-select
          ref="auxSelect"
          v-model="auxCols"
          :options="auxOptions"
          placeholder="Select auxiliary columns"
          display="chip"
          fluid
        />
      </label>

      <label class="field">
        <span class="label">Known-future columns (optional)</span>
        <multi-select
          ref="knownFutureSelect"
          v-model="knownFutureCols"
          :options="auxCols"
          :disabled="!auxCols.length"
          placeholder="Values you'll supply at prediction time"
          display="chip"
          fluid
        />
      </label>

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
    </div>

    <div v-if="!hasKnownFuture" class="preview">
      <span class="preview-title">Training preview (optional)</span>
      <p class="preview-sub">
        Extend the training chart with a forecast up to a future date. This never changes the saved
        model.
      </p>
      <div class="preview-controls">
        <label class="field">
          <span class="label">Forecast up to</span>
          <date-picker
            ref="previewDate"
            v-model="previewEndDate"
            :min-date="lastHistoricalDate ?? undefined"
            date-format="yy-mm-dd"
            placeholder="Select end date"
            show-icon
            fluid
          />
          <small v-if="previewDateInvalid" class="error" data-testid="error-preview-date">
            The end date must be after the last historical date.
          </small>
        </label>
        <label class="field">
          <span class="label">Display</span>
          <select-button
            ref="previewMode"
            v-model="previewMode"
            :options="PREVIEW_MODES"
            option-label="label"
            option-value="value"
            :allow-empty="false"
          />
        </label>
      </div>
    </div>
    <p v-else class="preview-hint" data-testid="preview-hint">
      Training preview is unavailable with known-future columns — their future values don't exist
      yet. Use the Model Evaluation step to re-forecast once you can supply them.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import MultiSelect from 'primevue/multiselect'
import DatePicker from 'primevue/datepicker'
import SelectButton from 'primevue/selectbutton'
import type { ForecastingFrequency } from '@/lib/data-processing/interfaces'
import {
  detectDateColumns,
  isDateColumn,
  lastDate,
  periodsBetween,
  type ForecastPreviewMode,
  type ForecastSetupConfig,
  type ForecastSetupState,
} from '@/lib/data-processing/forecasting-setup'

type Props = {
  columns: string[]
  rows: Record<string, unknown>[]
}

const props = defineProps<Props>()
const emit = defineEmits<{ change: [ForecastSetupState] }>()

const FREQUENCIES: { label: string; value: ForecastingFrequency }[] = [
  { label: 'Day', value: 'day' },
  { label: 'Week', value: 'week' },
  { label: 'Month', value: 'month' },
  { label: 'Quarter', value: 'quarter' },
  { label: 'Year', value: 'year' },
]
const PREVIEW_MODES: { label: string; value: ForecastPreviewMode }[] = [
  { label: 'Whole period', value: 'whole' },
  { label: 'Selected date only', value: 'single' },
]

const dateCol = ref('')
const targetCol = ref('')
const auxCols = ref<string[]>([])
const knownFutureCols = ref<string[]>([])
const frequency = ref<ForecastingFrequency>('month')
const previewEndDate = ref<Date | null>(null)
const previewMode = ref<ForecastPreviewMode>('whole')

const auxOptions = computed(() =>
  props.columns.filter((column) => column !== dateCol.value && column !== targetCol.value),
)
const hasKnownFuture = computed(() => knownFutureCols.value.length > 0)
const lastHistoricalDate = computed(() =>
  dateCol.value ? lastDate(props.rows, dateCol.value) : null,
)

const dateNotParseable = computed(() => !dateCol.value || !isDateColumn(props.rows, dateCol.value))
const sameDateTarget = computed(() => !!dateCol.value && dateCol.value === targetCol.value)
const previewDateInvalid = computed(
  () =>
    !hasKnownFuture.value &&
    !!previewEndDate.value &&
    !!lastHistoricalDate.value &&
    previewEndDate.value.getTime() <= lastHistoricalDate.value.getTime(),
)
const isValid = computed(
  () =>
    !dateNotParseable.value &&
    !sameDateTarget.value &&
    !!targetCol.value &&
    !previewDateInvalid.value,
)

const previewHorizon = computed<number | null>(() => {
  if (hasKnownFuture.value || !previewEndDate.value || !lastHistoricalDate.value) return null
  const horizon = periodsBetween(lastHistoricalDate.value, previewEndDate.value, frequency.value)
  return horizon > 0 ? horizon : null
})

const config = computed<ForecastSetupConfig>(() => ({
  date_col: dateCol.value,
  target_col: targetCol.value,
  aux_cols: [...auxCols.value],
  known_future_cols: [...knownFutureCols.value],
  frequency: frequency.value,
  preview_horizon: previewHorizon.value,
}))

watch([dateCol, targetCol], () => {
  auxCols.value = auxCols.value.filter(
    (column) => column !== dateCol.value && column !== targetCol.value,
  )
})
watch(auxCols, () => {
  knownFutureCols.value = knownFutureCols.value.filter((column) => auxCols.value.includes(column))
})

watch(
  () => props.columns,
  (columns) => {
    if (!columns.length) return
    const detected = detectDateColumns(props.rows, columns)
    dateCol.value = detected[0] ?? columns[0]
    const nonDate = columns.filter((column) => column !== dateCol.value)
    targetCol.value = nonDate[0] ?? ''
  },
  { immediate: true },
)

watch(
  [config, previewMode, isValid],
  () =>
    emit('change', {
      config: config.value,
      previewMode: previewMode.value,
      isValid: isValid.value,
    }),
  { immediate: true, deep: true },
)
</script>

<style scoped>
.setup {
  padding-top: 32px;
  padding-bottom: 32px;
}

.headings {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sub-title {
  color: var(--p-text-muted-color);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
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

.error {
  color: var(--p-message-error-color, var(--p-red-500));
  font-size: 13px;
}

.preview {
  margin-top: 32px;
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
}

.preview-title {
  font-weight: 500;
}

.preview-sub {
  margin: 8px 0 16px;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.preview-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.preview-hint {
  margin-top: 32px;
  padding: 16px;
  border-radius: 8px;
  background-color: var(--p-content-hover-background);
  color: var(--p-text-muted-color);
  font-size: 14px;
}

@media (max-width: 768px) {
  .grid,
  .preview-controls {
    grid-template-columns: 1fr;
  }
}
</style>
