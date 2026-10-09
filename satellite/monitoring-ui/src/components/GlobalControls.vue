<template>
  <div class="controls" data-testid="global-controls">
    <div ref="rangeControl" class="control range-control">
      <span class="control-label">Window</span>
      <div class="segmented" role="group" aria-label="Window">
        <button
          v-for="option in windowOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: !customActive && dimensions.window === option }"
          :data-testid="`window-${option}`"
          @click="$emit('update:window', option)"
        >
          {{ option }}
        </button>
        <button
          type="button"
          class="segment custom-segment"
          :class="{ active: customActive }"
          data-testid="window-custom"
          :aria-expanded="pickerOpen"
          @click="togglePicker"
        >
          <CalendarDays :size="13" />
          {{ customActive ? customLabel : 'Custom' }}
        </button>
      </div>

      <!-- Own calendar, not the browser's grey dropdown: the grid, the range
           highlight and the time fields all speak the design system. Retention
           holds 30 days, so the grid cannot reach further back. -->
      <div v-if="pickerOpen" class="range-anchor">
        <DateRangePicker
          :key="pickerSession"
          :start="dimensions.start"
          :end="dimensions.end"
          :clearable="customActive"
          @apply="applyRange"
          @clear="clearRange"
        />
      </div>
    </div>

    <div class="control">
      <span class="control-label">Severity</span>
      <div class="segmented" role="group" aria-label="Severity">
        <button
          v-for="option in severityOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: dimensions.severity === option }"
          :data-testid="`severity-${option}`"
          @click="$emit('update:severity', option)"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <!-- One refresh story: the manual button and its auto cadence sit together. -->
    <div class="control refresh-group">
      <button type="button" class="refresh" data-testid="refresh" @click="$emit('refresh')">
        <RefreshCw :size="14" />
        Refresh
      </button>
      <div class="segmented" role="group" aria-label="Auto-refresh">
        <button
          v-for="option in autoOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: autoRefresh === option }"
          :data-testid="`auto-${option}`"
          @click="$emit('update:auto', option)"
        >
          {{ autoLabel(option) }}
        </button>
      </div>
    </div>

    <button
      type="button"
      class="compare"
      :class="{ active: compareOn }"
      data-testid="compare-button"
      @click="$emit('open-compare')"
    >
      <ArrowLeftRight :size="14" />
      Compare
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowLeftRight, CalendarDays, RefreshCw } from 'lucide-vue-next'
import { Compare, SeverityFilter, Window, type Dimensions } from '@/api/types'
import { AUTO_REFRESH_OPTIONS, type AutoRefreshSeconds } from '@/composables/useMonitoringDashboard'
import DateRangePicker from '@/components/DateRangePicker.vue'

const props = defineProps<{ dimensions: Dimensions; autoRefresh: AutoRefreshSeconds }>()
const emit = defineEmits<{
  'update:window': [Window]
  'update:range': [string | null, string | null]
  'update:severity': [SeverityFilter]
  'update:auto': [AutoRefreshSeconds]
  'open-compare': []
  refresh: []
}>()

const compareOn = computed(
  () => props.dimensions.compare === Compare.PREVIOUS || props.dimensions.compare === Compare.CUSTOM,
)

const windowOptions = [Window.H24, Window.D7, Window.D30]
const severityOptions = [SeverityFilter.ALL, SeverityFilter.WARNING, SeverityFilter.CRITICAL]

const customActive = computed(() => props.dimensions.start !== null && props.dimensions.end !== null)

const pickerOpen = ref(false)
// Remounts the calendar per opening, so it re-anchors on the current selection.
const pickerSession = ref(0)
const rangeControl = ref<HTMLElement | null>(null)

function togglePicker(): void {
  pickerOpen.value = !pickerOpen.value
  if (pickerOpen.value) pickerSession.value += 1
}

// Outside click or Escape dismisses without applying.
function onPointerDown(event: PointerEvent) {
  if (!rangeControl.value?.contains(event.target as Node)) pickerOpen.value = false
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') pickerOpen.value = false
}
watch(pickerOpen, (open) => {
  if (open) {
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('pointerdown', onPointerDown)
    document.removeEventListener('keydown', onKeydown)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  document.removeEventListener('keydown', onKeydown)
})

function applyRange(start: string, end: string): void {
  emit('update:range', start, end)
  pickerOpen.value = false
}

function clearRange(): void {
  emit('update:range', null, null)
  pickerOpen.value = false
}

// A preset click elsewhere leaves custom mode; close the stale draft.
watch(customActive, (active) => {
  if (!active) pickerOpen.value = false
})

const customLabel = computed(() => {
  if (!customActive.value) return ''
  const fmt = (iso: string | null) => {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }
  return `${fmt(props.dimensions.start)} — ${fmt(props.dimensions.end)}`
})
const autoOptions = AUTO_REFRESH_OPTIONS

function autoLabel(seconds: AutoRefreshSeconds): string {
  if (seconds === 0) return 'off'
  return seconds < 60 ? `${seconds}s` : `${seconds / 60}m`
}
</script>

<style scoped>
.range-control {
  position: relative;
}
.range-anchor {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 30;
}
.custom-segment {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--luml-space-5);
}
.control {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
}
.control-label {
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  overflow: hidden;
  background: var(--luml-bg-card);
}
.segment {
  border: none;
  background: transparent;
  padding: 7px 14px;
  font: inherit;
  font-size: 13px;
  color: var(--luml-fg);
  cursor: pointer;
  text-transform: capitalize;
}
.segment + .segment {
  border-left: 1px solid var(--luml-border);
}
.segment.active {
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font-weight: 500;
}
.compare {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
  cursor: pointer;
}
.compare:hover {
  background: var(--luml-bg-hover);
}
.compare.active {
  background: var(--luml-brand);
  border-color: var(--luml-brand);
  color: var(--luml-brand-contrast);
}
.refresh-group {
  gap: var(--luml-space-3);
}
.refresh {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  padding: 7px 14px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.refresh:hover {
  background: var(--luml-bg-hover);
}
</style>
