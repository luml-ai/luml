<template>
  <div class="picker" data-testid="range-popover">
    <div class="cal-head">
      <button
        type="button"
        class="nav"
        aria-label="Previous month"
        data-testid="cal-prev"
        :disabled="!canGoPrev"
        @click="shiftMonth(-1)"
      >
        <ChevronLeft :size="15" />
      </button>
      <span class="month-label">{{ monthLabel }}</span>
      <button
        type="button"
        class="nav"
        aria-label="Next month"
        data-testid="cal-next"
        :disabled="!canGoNext"
        @click="shiftMonth(1)"
      >
        <ChevronRight :size="15" />
      </button>
    </div>

    <div class="grid">
      <span v-for="name in weekdayNames" :key="name" class="weekday">{{ name }}</span>
      <button
        v-for="day in days"
        :key="day.key"
        type="button"
        class="day"
        :class="{
          out: day.outsideMonth,
          today: day.isToday,
          'range-start': day.isStart,
          'range-end': day.isEnd,
          'in-range': day.inRange,
        }"
        :disabled="day.disabled"
        :data-testid="`cal-day-${day.key}`"
        @click="pickDay(day.date)"
        @mouseenter="hovered = day.date"
      >
        {{ day.date.getDate() }}
      </button>
    </div>

    <div class="times">
      <label class="time-field">
        <span>From</span>
        <input v-model="startTime" type="time" data-testid="range-start-time" />
      </label>
      <label class="time-field">
        <span>To</span>
        <input v-model="endTime" type="time" data-testid="range-end-time" />
      </label>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="standalone" class="actions">
      <button
        type="button"
        class="apply"
        data-testid="range-apply"
        :disabled="!valid"
        @click="apply"
      >
        Apply
      </button>
      <button
        v-if="clearable"
        type="button"
        class="clear"
        data-testid="range-clear"
        @click="$emit('clear')"
      >
        Back to 24h
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const RETENTION_DAYS = 30

const props = withDefaults(
  defineProps<{
    start: string | null
    end: string | null
    clearable: boolean
    /** Standalone shows its own Apply; embedded emits `change` and lets the host apply. */
    standalone?: boolean
  }>(),
  { standalone: true },
)
const emit = defineEmits<{ apply: [string, string]; clear: []; change: [string, string] }>()

const now = new Date()
const minDay = startOfDay(new Date(now.getTime() - RETENTION_DAYS * 86_400_000))
const maxDay = startOfDay(now)

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}
function sameDay(a: Date | null, b: Date | null): boolean {
  return a !== null && b !== null && a.getTime() === b.getTime()
}
function toTimeInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// Open on what is already selected, or on the last 24 hours.
const initialStart = props.start ? new Date(props.start) : new Date(now.getTime() - 86_400_000)
const initialEnd = props.end ? new Date(props.end) : now

const startDay = ref<Date | null>(startOfDay(initialStart))
const endDay = ref<Date | null>(startOfDay(initialEnd))
const startTime = ref(toTimeInput(initialStart))
const endTime = ref(toTimeInput(initialEnd))
const viewMonth = ref(new Date(initialEnd.getFullYear(), initialEnd.getMonth(), 1))
const hovered = ref<Date | null>(null)

const monthLabel = computed(() =>
  viewMonth.value.toLocaleString(undefined, { month: 'long', year: 'numeric' }),
)

const weekdayNames = computed(() => {
  // Monday-first, from the locale.
  const monday = new Date(2024, 0, 1) // a Monday
  return Array.from({ length: 7 }, (_, i) =>
    new Date(monday.getTime() + i * 86_400_000).toLocaleString(undefined, { weekday: 'short' }),
  )
})

const canGoPrev = computed(() => {
  const first = viewMonth.value
  return new Date(first.getFullYear(), first.getMonth(), 0) >= minDay
})
const canGoNext = computed(() => {
  const first = viewMonth.value
  return new Date(first.getFullYear(), first.getMonth() + 1, 1) <= maxDay
})

function shiftMonth(step: number): void {
  const current = viewMonth.value
  viewMonth.value = new Date(current.getFullYear(), current.getMonth() + step, 1)
}

interface DayCell {
  key: string
  date: Date
  outsideMonth: boolean
  disabled: boolean
  isToday: boolean
  isStart: boolean
  isEnd: boolean
  inRange: boolean
}

const days = computed<DayCell[]>(() => {
  const first = viewMonth.value
  // Monday-first offset of the month's first day.
  const lead = (first.getDay() + 6) % 7
  const cells: DayCell[] = []
  const today = startOfDay(new Date())
  // While only the start is picked, hovering previews the range up to the cursor.
  const previewEnd =
    endDay.value ?? (startDay.value && hovered.value && hovered.value >= startDay.value ? hovered.value : null)
  for (let i = 0; i < 42; i++) {
    const date = new Date(first.getFullYear(), first.getMonth(), 1 - lead + i)
    const isStart = sameDay(date, startDay.value)
    const isEnd = sameDay(date, endDay.value ?? previewEnd)
    const inRange =
      startDay.value !== null &&
      previewEnd !== null &&
      date > startDay.value &&
      date < previewEnd
    cells.push({
      key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
      date,
      outsideMonth: date.getMonth() !== first.getMonth(),
      disabled: date < minDay || date > maxDay,
      isToday: sameDay(date, today),
      isStart,
      isEnd,
      inRange,
    })
  }
  return cells
})

function pickDay(date: Date): void {
  // First click anchors the start; the second completes the range. A click before
  // the anchor, or with a range already complete, starts over.
  if (startDay.value === null || endDay.value !== null || date < startDay.value) {
    startDay.value = date
    endDay.value = null
    return
  }
  endDay.value = date
}

function combine(day: Date | null, time: string): Date | null {
  if (day === null || !time) return null
  const [hours, minutes] = time.split(':').map(Number)
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), hours, minutes)
}

const draft = computed(() => ({
  start: combine(startDay.value, startTime.value),
  end: combine(endDay.value ?? startDay.value, endTime.value),
}))

const error = computed(() => {
  const { start, end } = draft.value
  if (!start || !end) return null
  if (end <= start) return 'End must be after start'
  if (end.getTime() - start.getTime() > RETENTION_DAYS * 86_400_000) {
    return 'Data is retained for 30 days — pick a narrower range'
  }
  return null
})
const valid = computed(() => draft.value.start !== null && draft.value.end !== null && error.value === null)

function apply(): void {
  const { start, end } = draft.value
  if (!start || !end) return
  emit('apply', start.toISOString(), end.toISOString())
}

// Embedded mode reports every valid selection upward, including the initial one.
watch(
  [valid, draft],
  () => {
    if (props.standalone || !valid.value) return
    const { start, end } = draft.value
    if (start && end) emit('change', start.toISOString(), end.toISOString())
  },
  { immediate: true, deep: true },
)
</script>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 292px;
  padding: 16px;
  background: var(--luml-bg-card);
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-lg);
  box-shadow: var(--luml-shadow-card), 0 12px 32px rgba(28, 43, 64, 0.16);
}
.cal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.month-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--luml-fg-strong);
  text-transform: capitalize;
}
.nav {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: transparent;
  color: var(--luml-fg);
  cursor: pointer;
}
.nav:hover:not(:disabled) {
  background: var(--luml-bg-hover);
}
.nav:disabled {
  opacity: 0.35;
  cursor: default;
}
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px 0;
}
.weekday {
  padding: 4px 0;
  text-align: center;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.day {
  height: 32px;
  border: none;
  background: transparent;
  font: inherit;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
  color: var(--luml-fg);
  border-radius: var(--luml-radius-md);
  cursor: pointer;
}
.day:hover:not(:disabled):not(.range-start):not(.range-end) {
  background: var(--luml-bg-hover);
}
.day.out {
  color: var(--luml-fg-faint, var(--luml-surface-400));
}
.day:disabled {
  color: var(--luml-surface-300);
  cursor: default;
}
.day.today:not(.range-start):not(.range-end) {
  box-shadow: inset 0 0 0 1px var(--luml-border-strong);
}
.day.in-range {
  background: var(--luml-brand-tint);
  border-radius: 0;
}
.day.range-start,
.day.range-end {
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font-weight: 600;
}
.day.range-start:not(.range-end) {
  border-radius: var(--luml-radius-md) 0 0 var(--luml-radius-md);
}
.day.range-end:not(.range-start) {
  border-radius: 0 var(--luml-radius-md) var(--luml-radius-md) 0;
}
.times {
  display: flex;
  gap: 10px;
}
.time-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.time-field span {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.time-field input {
  font: inherit;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--luml-fg-strong);
  background: var(--luml-bg-card);
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  padding: 7px 9px;
  transition: border-color 0.12s ease;
}
.time-field input:hover {
  border-color: var(--luml-border-strong);
}
.time-field input:focus {
  outline: none;
  border-color: var(--luml-brand);
}
.time-field input::-webkit-calendar-picker-indicator {
  display: none;
}
.error {
  margin: 0;
  font-size: 11.5px;
  color: var(--luml-danger-tint-fg);
}
.actions {
  display: flex;
  gap: 8px;
}
.apply {
  flex: 1;
  border: none;
  border-radius: var(--luml-radius-md);
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  padding: 8px 14px;
  cursor: pointer;
}
.apply:hover:not(:disabled) {
  background: var(--luml-brand-hover);
}
.apply:disabled {
  opacity: 0.45;
  cursor: default;
}
.clear {
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: transparent;
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  padding: 8px 12px;
  cursor: pointer;
}
.clear:hover {
  background: var(--luml-bg-hover);
}
</style>
