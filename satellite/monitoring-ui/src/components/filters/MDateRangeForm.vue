<template>
  <div class="range-form">
    <div class="range-columns">
      <div class="range-column">
        <span class="range-label">From</span>
        <div class="date-field">
          <Calendar :size="12.25" class="date-field-icon" />
          <DatePicker
            v-model="fromDate"
            size="small"
            date-format="mm/dd/yy"
            placeholder="10/27/2026"
            show-icon
            icon-display="input"
            append-to="self"
            aria-label="From date"
            :min-date="minDate"
            :max-date="maxDate"
            :pt="rangePt"
            fluid
            @date-select="onFromSelect"
            @hide="onFromHide"
          >
            <template #inputicon="{ clickCallback }">
              <ChevronDown :size="12.25" class="date-field-chevron" @click="clickCallback" />
            </template>
          </DatePicker>
        </div>
        <DatePicker
          v-model="fromTime"
          size="small"
          time-only
          hour-format="12"
          placeholder="06:02 PM"
          aria-label="From time"
          fluid
        />
      </div>
      <div class="range-column">
        <span class="range-label">To</span>
        <div ref="toField" class="date-field">
          <Calendar :size="12.25" class="date-field-icon" />
          <DatePicker
            v-model="toDate"
            size="small"
            date-format="mm/dd/yy"
            placeholder="10/27/2026"
            show-icon
            icon-display="input"
            append-to="self"
            aria-label="To date"
            :min-date="fromDate ?? minDate"
            :max-date="maxDate"
            :pt="rangePt"
            fluid
          >
            <template #inputicon="{ clickCallback }">
              <ChevronDown :size="12.25" class="date-field-chevron" @click="clickCallback" />
            </template>
          </DatePicker>
        </div>
        <DatePicker
          v-model="toTime"
          size="small"
          time-only
          hour-format="12"
          placeholder="06:02 PM"
          aria-label="To time"
          fluid
        />
      </div>
    </div>
    <Message
      v-if="rangeNotice"
      :severity="rangeNotice.severity"
      size="small"
      variant="simple"
      class="range-notice"
      role="status"
    >
      {{ rangeNotice.text }}
    </Message>
    <Button
      class="apply-button"
      label="Apply"
      severity="secondary"
      fluid
      :disabled="!draftRange"
      @click="onApply"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import { RETENTION_DAYS } from '@/constants/filters'
import { Calendar, ChevronDown } from 'lucide-vue-next'

interface CalendarDate {
  day: number
  month: number
  year: number
  otherMonth: boolean
}

const props = defineProps<{
  start: string | null
  end: string | null
}>()

const emit = defineEmits<{
  apply: [range: { start: Date; end: Date }]
}>()

const toField = useTemplateRef<HTMLDivElement>('toField')

const initialStart = props.start ? new Date(props.start) : null
const initialEnd = props.end ? new Date(props.end) : null

const fromDate = ref<Date | null>(initialStart)
const fromTime = ref<Date | null>(initialStart)
const toDate = ref<Date | null>(initialEnd)
const toTime = ref<Date | null>(initialEnd)
const shouldFocusTo = ref(false)

const maxDate = new Date()
const minDate = new Date(maxDate.getTime() - RETENTION_DAYS * 24 * 60 * 60 * 1000)

const boundFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

const rangeBounds = computed(() => {
  if (!fromDate.value) return null
  const start = toDayKey(fromDate.value)
  const end = toDate.value ? toDayKey(toDate.value) : start
  return { start, end }
})

const rangePt = computed(() => ({
  dayCell: ({ context }: { context: { date: CalendarDate } }) => {
    const bounds = rangeBounds.value
    if (!bounds || context.date.otherMonth) return {}
    const key = context.date.year * 10000 + context.date.month * 100 + context.date.day
    if (key < bounds.start || key > bounds.end) return {}
    return {
      class: {
        'range-day': true,
        'range-day-start': key === bounds.start,
        'range-day-end': key === bounds.end,
      },
    }
  },
}))

const enteredRange = computed(() => {
  if (!fromDate.value || !toDate.value) return null
  return {
    start: combineDateTime(fromDate.value, fromTime.value, 'start'),
    end: combineDateTime(toDate.value, toTime.value, 'end'),
  }
})

const draftRange = computed(() => {
  if (!enteredRange.value) return null
  const start = clampDate(enteredRange.value.start)
  const end = clampDate(enteredRange.value.end)
  return start < end ? { start, end } : null
})

const rangeNotice = computed<{ severity: 'error' | 'secondary'; text: string } | null>(() => {
  const entered = enteredRange.value
  if (!entered) return null
  if (entered.end <= entered.start) {
    return { severity: 'error', text: 'End must be later than start' }
  }
  if (!draftRange.value) {
    return { severity: 'error', text: `Pick a period within the last ${RETENTION_DAYS} days` }
  }
  if (entered.start < minDate) {
    return {
      severity: 'secondary',
      text: `Start will be moved to ${formatBound(minDate)}, the oldest retained data`,
    }
  }
  if (entered.end > maxDate) {
    return { severity: 'secondary', text: `End will be moved to now (${formatBound(maxDate)})` }
  }
  return null
})

function toDayKey(date: Date) {
  return date.getFullYear() * 10000 + date.getMonth() * 100 + date.getDate()
}

function onFromSelect(date: Date) {
  if (toDate.value && toDate.value < date) toDate.value = null
  shouldFocusTo.value = true
}

function onFromHide() {
  if (!shouldFocusTo.value) return
  shouldFocusTo.value = false
  toField.value?.querySelector('input')?.focus()
}

function combineDateTime(date: Date, time: Date | null, edge: 'start' | 'end') {
  const result = new Date(date)
  const hours = time ? time.getHours() : edge === 'start' ? 0 : 23
  const minutes = time ? time.getMinutes() : edge === 'start' ? 0 : 59
  if (edge === 'start') result.setHours(hours, minutes, 0, 0)
  else result.setHours(hours, minutes, 59, 999)
  return result
}

function formatBound(date: Date) {
  return boundFormatter.format(date)
}

function clampDate(date: Date) {
  const time = Math.min(Math.max(date.getTime(), minDate.getTime()), maxDate.getTime())
  return new Date(time)
}

function onApply() {
  if (!draftRange.value) return
  emit('apply', draftRange.value)
}
</script>

<style scoped>
.range-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.range-columns {
  display: flex;
  gap: 10px;
}

.range-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 140px;
}

.range-label {
  margin-bottom: -3px;
  font-size: 14px;
  line-height: 21px;
}

.date-field {
  position: relative;
}

.date-field-chevron {
  color: var(--p-surface-400);
  cursor: pointer;
}

.range-notice {
  max-width: 290px;
  margin-block: -8px;
}

.date-field-icon {
  color: var(--p-surface-400);
  position: absolute;
  top: 50%;
  left: 9px;
  z-index: 1;
  transform: translateY(-50%);
  pointer-events: none;
}

.range-column :deep(.p-datepicker .p-datepicker-input) {
  height: 27.5px;
  padding-inline: 9px;
  font-size: 12.25px;
}

.date-field :deep(.p-datepicker .p-datepicker-input) {
  padding-inline: 30px 27px;
}

.date-field :deep(.p-datepicker .p-datepicker-input-icon-container) {
  inset-inline-end: 9px;
  margin-block-start: -6.125px;
}

.range-column :deep(.range-day) {
  padding-inline: 0;
}

.range-column :deep(.range-day .p-datepicker-day) {
  width: 100%;
  border-radius: 0;
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

.range-column :deep(.range-day-start .p-datepicker-day) {
  border-start-start-radius: 14px;
  border-end-start-radius: 14px;
}

.range-column :deep(.range-day-end .p-datepicker-day) {
  border-start-end-radius: 14px;
  border-end-end-radius: 14px;
}

.apply-button {
  background-color: var(--p-primary-100);
  border-color: var(--p-primary-100);
  color: var(--p-surface-600);
}
</style>
