import { computed, ref, watch, type Ref } from 'vue'
import type {
  ForecastingAggregation,
  ForecastingFrequency,
} from '@/lib/data-processing/interfaces'
import {
  detectDateColumns,
  isDateColumn,
  isNumericColumn,
  lastDate,
  periodsBetween,
  toUtcDay,
  type ForecastSetupConfig,
} from '@/lib/data-processing/forecasting-setup'

export type ForecastColumnRole = 'date' | 'target' | 'aux' | 'known_future' | null

export const useForecastSetup = (
  columns: Ref<string[]>,
  rows: Ref<Record<string, unknown>[]>,
) => {
  const dateCol = ref('')
  const targetCol = ref('')
  const auxCols = ref<string[]>([])
  const knownFutureCols = ref<string[]>([])
  const frequency = ref<ForecastingFrequency>('month')
  const aggregation = ref<ForecastingAggregation>('mean')
  const previewEndDate = ref<Date | null>(null)

  const hasKnownFuture = computed(() => knownFutureCols.value.length > 0)
  const lastHistoricalDate = computed(() =>
    dateCol.value ? lastDate(rows.value, dateCol.value) : null,
  )
  const dateNotParseable = computed(
    () => !dateCol.value || !isDateColumn(rows.value, dateCol.value),
  )
  const targetNotNumeric = computed(
    () => !!targetCol.value && !isNumericColumn(rows.value, targetCol.value),
  )
  const previewDateInvalid = computed(
    () =>
      !hasKnownFuture.value &&
      !!previewEndDate.value &&
      !!lastHistoricalDate.value &&
      toUtcDay(previewEndDate.value).getTime() <= toUtcDay(lastHistoricalDate.value).getTime(),
  )
  const isValid = computed(
    () =>
      !dateNotParseable.value &&
      !!targetCol.value &&
      targetCol.value !== dateCol.value &&
      !targetNotNumeric.value &&
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
    aggregation: aggregation.value,
  }))

  function columnRole(column: string): ForecastColumnRole {
    if (column === dateCol.value) return 'date'
    if (column === targetCol.value) return 'target'
    if (knownFutureCols.value.includes(column)) return 'known_future'
    if (auxCols.value.includes(column)) return 'aux'
    return null
  }

  // Assigning one role's column to the other swaps the two roles, so the date
  // and target columns can be reassigned directly from their own header menus.
  function setDateColumn(column: string) {
    if (column === targetCol.value) targetCol.value = dateCol.value
    dateCol.value = column
  }

  function setTargetColumn(column: string) {
    if (column === dateCol.value) dateCol.value = targetCol.value
    targetCol.value = column
  }

  function toggleAux(column: string) {
    if (column === dateCol.value || column === targetCol.value) return
    if (auxCols.value.includes(column)) {
      auxCols.value = auxCols.value.filter((item) => item !== column)
    } else {
      auxCols.value = [...auxCols.value, column]
    }
  }

  function toggleKnownFuture(column: string) {
    if (!auxCols.value.includes(column)) return
    if (knownFutureCols.value.includes(column)) {
      knownFutureCols.value = knownFutureCols.value.filter((item) => item !== column)
    } else {
      knownFutureCols.value = [...knownFutureCols.value, column]
    }
  }

  watch([dateCol, targetCol], () => {
    auxCols.value = auxCols.value.filter(
      (column) => column !== dateCol.value && column !== targetCol.value,
    )
  })
  watch(auxCols, () => {
    knownFutureCols.value = knownFutureCols.value.filter((column) =>
      auxCols.value.includes(column),
    )
  })

  // Re-detect roles only for columns that disappeared (e.g. hidden in the
  // preview table) so edits elsewhere keep the user's selections.
  watch(
    columns,
    (cols) => {
      if (!cols.length) return
      if (!cols.includes(dateCol.value)) {
        const detected = detectDateColumns(rows.value, cols)
        dateCol.value = detected[0] ?? cols[0]
      }
      if (!cols.includes(targetCol.value) || targetCol.value === dateCol.value) {
        const nonDate = cols.filter((column) => column !== dateCol.value)
        targetCol.value =
          nonDate.find((column) => isNumericColumn(rows.value, column)) ?? nonDate[0] ?? ''
      }
      auxCols.value = auxCols.value.filter((column) => cols.includes(column))
    },
    { immediate: true },
  )

  return {
    dateCol,
    targetCol,
    auxCols,
    knownFutureCols,
    frequency,
    aggregation,
    previewEndDate,
    hasKnownFuture,
    lastHistoricalDate,
    dateNotParseable,
    targetNotNumeric,
    previewDateInvalid,
    previewHorizon,
    isValid,
    config,
    columnRole,
    setDateColumn,
    setTargetColumn,
    toggleAux,
    toggleKnownFuture,
  }
}
