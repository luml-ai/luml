<template>
  <DetailDrawer
    :open="open"
    feature="Compare"
    kind="mode"
    caption="Pick what this window is measured against"
    eyebrow="Comparison"
    testid="compare-drawer"
    @close="$emit('close')"
  >
    <div class="compare-body">
      <p class="note">
        Drift metrics always measure against the training reference. This adds a second
        stretch of runtime next to the current one: deltas on the cards, a ghost line on
        the charts.
      </p>

      <div class="modes" role="radiogroup" aria-label="Compare mode">
        <button
          v-for="mode in modes"
          :key="mode.key"
          type="button"
          class="mode"
          :class="{ selected: selected === mode.key }"
          :data-testid="`compare-mode-${mode.key}`"
          role="radio"
          :aria-checked="selected === mode.key"
          @click="selected = mode.key"
        >
          <span class="mode-title">{{ mode.title }}</span>
          <span class="mode-hint">{{ mode.hint }}</span>
        </button>
      </div>

      <!-- Custom mode picks BOTH stretches: what to look at, and what to hold it against. -->
      <template v-if="selected === Compare.CUSTOM">
        <div class="period">
          <p class="period-title">First period — shown on the page</p>
          <DateRangePicker
            :key="`a-${pickerSession}`"
            class="embedded-picker"
            :start="dimensions.start"
            :end="dimensions.end"
            :clearable="false"
            :standalone="false"
            @change="onPeriodA"
          />
        </div>
        <div class="period">
          <p class="period-title">Second period — compared against</p>
          <DateRangePicker
            :key="`b-${pickerSession}`"
            class="embedded-picker"
            :start="dimensions.compareStart"
            :end="dimensions.compareEnd"
            :clearable="false"
            :standalone="false"
            @change="onPeriodB"
          />
        </div>
      </template>

      <button
        type="button"
        class="apply"
        data-testid="compare-apply"
        :disabled="!applyReady"
        @click="applySelection"
      >
        Apply
      </button>
    </div>
  </DetailDrawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Compare, type Dimensions } from '@/api/types'
import DetailDrawer from '@/components/DetailDrawer.vue'
import DateRangePicker from '@/components/DateRangePicker.vue'

const props = defineProps<{ open: boolean; dimensions: Dimensions }>()

interface ComparePeriods {
  start: string
  end: string
  compareStart: string
  compareEnd: string
}

const emit = defineEmits<{ close: []; apply: [Compare, ComparePeriods | null] }>()

const modes = [
  { key: Compare.OFF, title: 'Off', hint: 'Just the selected window, no baseline' },
  {
    key: Compare.PREVIOUS,
    title: 'Previous period',
    hint: 'The same length of time right before the current window',
  },
  {
    key: Compare.CUSTOM,
    title: 'Custom period',
    hint: 'Two stretches from the last 30 days, held against each other',
  },
]

const selected = ref<Compare>(Compare.OFF)
const pickerSession = ref(0)

// Opening reflects what is currently applied, not what was left from last time.
watch(
  () => props.open,
  (open) => {
    if (!open) return
    selected.value =
      props.dimensions.compare === Compare.REFERENCE ? Compare.OFF : props.dimensions.compare
    pickerSession.value += 1
  },
)

const periodA = ref<{ start: string; end: string } | null>(null)
const periodB = ref<{ start: string; end: string } | null>(null)

function onPeriodA(start: string, end: string): void {
  periodA.value = { start, end }
}
function onPeriodB(start: string, end: string): void {
  periodB.value = { start, end }
}

const applyReady = computed(
  () =>
    selected.value !== Compare.CUSTOM || (periodA.value !== null && periodB.value !== null),
)

function applySelection(): void {
  if (selected.value !== Compare.CUSTOM) {
    emit('apply', selected.value, null)
    return
  }
  if (!periodA.value || !periodB.value) return
  emit('apply', Compare.CUSTOM, {
    start: periodA.value.start,
    end: periodA.value.end,
    compareStart: periodB.value.start,
    compareEnd: periodB.value.end,
  })
}
</script>

<style scoped>
.compare-body {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.note {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--luml-fg-muted);
}
.modes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mode {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  padding: 11px 13px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  font: inherit;
  cursor: pointer;
  transition: border-color 0.12s ease;
}
.mode:hover {
  border-color: var(--luml-border-strong);
}
.mode.selected {
  border-color: var(--luml-brand);
  box-shadow: inset 0 0 0 1px var(--luml-brand);
}
.mode-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.mode-hint {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.period {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.period-title {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.embedded-picker {
  /* the drawer already provides the card chrome */
  box-shadow: none;
  width: 100%;
}
.apply:disabled {
  opacity: 0.45;
  cursor: default;
}
.apply {
  border: none;
  border-radius: var(--luml-radius-md);
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  padding: 9px 14px;
  cursor: pointer;
}
.apply:hover {
  background: var(--luml-brand-hover);
}
</style>
