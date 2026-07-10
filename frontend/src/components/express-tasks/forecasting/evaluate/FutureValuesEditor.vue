<template>
  <div class="editor">
    <div class="editor-head">
      <div>
        <p class="editor-title">Future values</p>
        <p class="editor-sub">
          Supply a value for every known-future feature on each forecast date. You can also upload a
          CSV of <code>{{ dateCol }}</code> + known-future columns to fill the grid.
        </p>
      </div>
      <label class="upload">
        <span>Upload CSV</span>
        <input
          ref="csvInput"
          type="file"
          accept=".csv"
          data-testid="future-csv"
          @change="onCsvChange"
        />
      </label>
    </div>

    <div class="table-wrap">
      <table class="grid">
        <thead>
          <tr>
            <th>{{ dateCol }}</th>
            <th v-for="col in columns" :key="col">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="date in dates" :key="date">
            <td class="date-cell">{{ date }}</td>
            <td v-for="col in columns" :key="col">
              <input
                type="number"
                step="any"
                class="cell-input"
                :class="{ invalid: !isFilled(date, col) }"
                :value="cellValue(date, col)"
                :data-testid="`cell-${date}-${col}`"
                @input="onInput(date, col, $event)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="!complete" class="hint" data-testid="future-incomplete">
      Enter a numeric value in every cell to enable forecasting.
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fromCSV } from 'arquero'
import type { ForecastingFrequency, ForecastingRecord } from '@/lib/data-processing/interfaces'
import { periodKey } from '@/lib/data-processing/forecasting-setup'

type Props = {
  dates: string[]
  columns: string[]
  dateCol: string
  frequency: ForecastingFrequency
}

const props = defineProps<Props>()
const emit = defineEmits<{ change: [{ complete: boolean; future: ForecastingRecord[] }] }>()

const csvInput = ref<HTMLInputElement | null>(null)
const values = ref<Record<string, Record<string, number | null>>>({})

function rebuild(): void {
  const next: Record<string, Record<string, number | null>> = {}
  for (const date of props.dates) {
    next[date] = {}
    for (const col of props.columns) {
      next[date][col] = values.value[date]?.[col] ?? null
    }
  }
  values.value = next
}

const complete = computed(
  () =>
    props.dates.length > 0 &&
    props.dates.every((date) =>
      props.columns.every((col) => Number.isFinite(values.value[date]?.[col])),
    ),
)

function buildFuture(): ForecastingRecord[] {
  return props.dates.map((date) => {
    const record: ForecastingRecord = { [props.dateCol]: date }
    for (const col of props.columns) record[col] = values.value[date][col] as number
    return record
  })
}

function isFilled(date: string, col: string): boolean {
  return Number.isFinite(values.value[date]?.[col])
}

function cellValue(date: string, col: string): number | string {
  const value = values.value[date]?.[col]
  return value === null || value === undefined ? '' : value
}

function onInput(date: string, col: string, event: Event): void {
  const raw = (event.target as HTMLInputElement).value
  values.value[date][col] = raw === '' ? null : Number(raw)
}

function applyRecords(records: Record<string, unknown>[]): void {
  const keyToDate = new Map(props.dates.map((date) => [periodKey(date, props.frequency), date]))
  for (const record of records) {
    const date = keyToDate.get(periodKey(record[props.dateCol], props.frequency) ?? '')
    if (!date) continue
    for (const col of props.columns) {
      const cell = record[col]
      if (cell === undefined || cell === null || cell === '') continue
      const num = Number(cell)
      if (Number.isFinite(num)) values.value[date][col] = num
    }
  }
}

async function onCsvChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  applyRecords(fromCSV(await file.text()).objects() as Record<string, unknown>[])
  input.value = ''
}

watch(() => [props.dates, props.columns], rebuild, { immediate: true, deep: true })
watch(
  [complete, values],
  () => emit('change', { complete: complete.value, future: complete.value ? buildFuture() : [] }),
  { immediate: true, deep: true },
)

defineExpose({ applyRecords })
</script>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.editor-title {
  font-weight: 500;
}

.editor-sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--p-text-muted-color);
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  white-space: nowrap;
}

.table-wrap {
  overflow: auto;
  max-height: 260px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
}

.grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.grid th,
.grid td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--p-content-border-color);
  text-align: left;
}

.grid th {
  position: sticky;
  top: 0;
  background-color: var(--p-content-background);
  font-weight: 500;
}

.date-cell {
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.cell-input {
  width: 100px;
  padding: 4px 8px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  background-color: var(--p-content-background);
  color: var(--p-text-color);
}

.cell-input.invalid {
  border-color: var(--p-message-error-color, var(--p-red-500));
}

.hint {
  font-size: 13px;
  color: var(--p-text-muted-color);
}
</style>
