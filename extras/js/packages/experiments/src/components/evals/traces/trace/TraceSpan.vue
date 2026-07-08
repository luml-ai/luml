<template>
  <div
    class="item"
    :style="{
      paddingLeft: 8 + 12 * nesting + 'px',
    }"
    :class="{
      selected: selectedSpanId === data.span_id,
    }"
    @click="$emit('select', data)"
  >
    <button v-if="data.children.length" class="button" @click.stop="spanOpened = !spanOpened">
      <component :is="spanOpened ? ChevronDown : ChevronRight" :size="14"></component>
    </button>
    <div v-else style="width: 35px; flex: 0 0 auto"></div>
    <div class="item-body">
      <div class="item-header">
        <h4 class="title">
          <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" class="icon" />
          <span>{{ data.name }}</span>
        </h4>
        <AnnotationsTag v-if="data.annotation_count" :count="data.annotation_count" />
      </div>
      <div class="info">
        <History :size="12" />
        <span>{{ time }}</span>
      </div>
      <div class="progress-wrapper">
        <div
          class="progress-plug"
          :style="{
            width: startProgress + '%',
          }"
        ></div>
        <ProgressBar
          :value="endProgress"
          :show-value="false"
          class="progress"
          :pt="{
            value: {
              style: {
                backgroundColor: spanTypeData.color,
              },
            },
          }"
        ></ProgressBar>
      </div>
    </div>
  </div>
  <div v-if="data.children.length && spanOpened" class="children">
    <TraceSpan
      v-for="item in data.children"
      :key="item.span_id"
      :data="item"
      :nesting="nesting + 1"
      :selected-span-id="selectedSpanId"
      :all-opened="allOpened"
      :min-span-time="minSpanTime"
      :max-span-time="maxSpanTime"
      @select="(payload: TraceSpanType) => $emit('select', payload)"
    ></TraceSpan>
  </div>
</template>

<script setup lang="ts">
import type { TraceSpan as TraceSpanType } from '@/interfaces/interfaces'
import { ProgressBar } from 'primevue'
import { ChevronDown, ChevronRight, History } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { getFormattedTime, getSpanTypeData } from '@/helpers/helpers'
import AnnotationsTag from '../../../annotations/AnnotationsTag.vue'

type Props = {
  data: TraceSpanType
  nesting: number
  selectedSpanId: string | undefined
  allOpened: boolean
  maxSpanTime: number | null
  minSpanTime: number | null
}

type Emits = {
  select: [TraceSpanType]
}

defineEmits<Emits>()
const props = defineProps<Props>()

const spanOpened = ref(true)

const spanTypeData = computed(() => {
  return getSpanTypeData(props.data.dfs_span_type)
})

const time = computed(() => {
  return getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano)
})

// Offset (start) and fill (end) as percentages of the trace's time range. An absent or
// zero range has no meaningful offset, so bars fall back to zero offset / full width
// rather than dividing by zero; a legitimate min/max of 0 is used, not treated as missing.
// Percentages are clamped so rounding-noisy timestamps can't push a bar outside the track.
function spanProgress(timeNano: number, fallback: number): number {
  const { minSpanTime, maxSpanTime } = props
  if (minSpanTime === null || maxSpanTime === null) return fallback
  const range = maxSpanTime - minSpanTime
  if (range <= 0) return fallback
  const percent = ((timeNano - minSpanTime) / range) * 100
  return Math.min(100, Math.max(0, percent))
}

const startProgress = computed(() => spanProgress(props.data.start_time_unix_nano, 0))
const endProgress = computed(() => spanProgress(props.data.end_time_unix_nano, 100))

watch(
  () => props.allOpened,
  (val) => {
    spanOpened.value = val
  },
)
</script>

<style scoped>
.item {
  padding: 8px;
  border-radius: 8px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  overflow: hidden;
  margin-bottom: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background-color 0.2s,
    box-shadow 0.2s;
}

.item.selected {
  border-color: var(--p-content-border-color);
  background: var(--p-content-background);
  box-shadow: var(--card-shadow);
  cursor: default;
}

.button {
  width: 25px;
  height: 25px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex: 0 0 auto;
  color: var(--p-datatable-row-toggle-button-color);
  border-radius: var(--p-button-border-radius);
  transition: background-color 0.2s;

  &:hover {
    background-color: var(--p-datatable-row-toggle-button-hover-background);
  }
}

.item-body {
  flex: 1 1 auto;
  overflow: hidden;
}

.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
}

.title span {
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.icon {
  flex: 0 0 auto;
}

.info {
  padding-left: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
  margin-bottom: 8px;
}

.progress {
  height: 4px;
}

.progress-wrapper {
  position: relative;
  border-radius: var(--p-progressbar-border-radius);
  overflow: hidden;
}

.progress-plug {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  height: 4px;
  background: var(--p-progressbar-background);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  overflow: hidden;
  gap: 10px;
}
</style>
