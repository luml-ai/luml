<template>
  <div
    class="item"
    :class="{ selected: selectedSpanId === data.span_id }"
    :style="{ paddingLeft: 8 + 12 * nesting + 'px' }"
    data-testid="trace-span-item"
    @click="$emit('select', data)"
  >
    <button
      v-if="data.children.length"
      type="button"
      class="toggle"
      :aria-label="spanOpened ? 'Collapse' : 'Expand'"
      @click.stop="spanOpened = !spanOpened"
    >
      <component :is="spanOpened ? ChevronDown : ChevronRight" :size="14" />
    </button>
    <div v-else class="toggle-spacer"></div>

    <div class="item-body">
      <div class="item-header">
        <h4 class="title">
          <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" class="icon" />
          <span>{{ data.name }}</span>
        </h4>
        <span v-if="data.status_code === 2" class="error-dot" title="Span failed"></span>
      </div>

      <div class="info">
        <History :size="12" />
        <span>{{ time }}</span>
      </div>

      <!-- Waterfall: offset from the trace start, width = the span's share of it. -->
      <div class="progress-wrapper">
        <div class="progress-track"></div>
        <div
          class="progress-bar"
          :style="{
            left: startProgress + '%',
            width: barWidth + '%',
            backgroundColor: spanTypeData.color,
          }"
        ></div>
      </div>
    </div>
  </div>

  <div v-if="data.children.length && spanOpened">
    <TraceSpanItem
      v-for="child in data.children"
      :key="child.span_id"
      :data="child"
      :nesting="nesting + 1"
      :selected-span-id="selectedSpanId"
      :all-opened="allOpened"
      :min-span-time="minSpanTime"
      :max-span-time="maxSpanTime"
      @select="(payload: TraceSpanNode) => $emit('select', payload)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronRight, History } from 'lucide-vue-next'
import type { TraceSpanNode } from '@/api/types'
import { getFormattedTime, getSpanTypeData } from '@/lib/spans'

const props = defineProps<{
  data: TraceSpanNode
  nesting: number
  selectedSpanId: string | undefined
  allOpened: boolean
  minSpanTime: number
  maxSpanTime: number
}>()

defineEmits<{ select: [TraceSpanNode] }>()

const spanOpened = ref(true)

const spanTypeData = computed(() => getSpanTypeData(props.data.dfs_span_type))

const time = computed(() =>
  getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano),
)

const traceDuration = computed(() => props.maxSpanTime - props.minSpanTime)

const startProgress = computed(() => {
  if (traceDuration.value <= 0) return 0
  return ((props.data.start_time_unix_nano - props.minSpanTime) / traceDuration.value) * 100
})

const barWidth = computed(() => {
  if (traceDuration.value <= 0) return 100
  const width =
    ((props.data.end_time_unix_nano - props.data.start_time_unix_nano) / traceDuration.value) * 100
  // Sub-millisecond spans would otherwise render as an invisible sliver.
  return Math.max(width, 1)
})

watch(
  () => props.allOpened,
  (value) => (spanOpened.value = value),
)
</script>

<style scoped>
.item {
  padding: 8px;
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: var(--luml-radius-md);
  cursor: pointer;
  transition:
    border-color 0.2s,
    background-color 0.2s;
}
.item:hover {
  background: var(--luml-bg-hover);
}
.item.selected {
  border-color: var(--luml-border);
  background: var(--luml-bg-card);
  cursor: default;
}
.toggle {
  width: 25px;
  height: 25px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--luml-radius-md);
  background: transparent;
  color: var(--luml-fg-muted);
  cursor: pointer;
}
.toggle:hover {
  background: var(--luml-surface-100);
}
.toggle-spacer {
  width: 25px;
  flex: 0 0 auto;
}
.item-body {
  flex: 1 1 auto;
  overflow: hidden;
}
.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
}
.title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.icon {
  flex: 0 0 auto;
}
.error-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--luml-danger);
}
.info {
  padding-left: 8px;
  margin-bottom: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--luml-fg-muted);
  font-size: 12px;
}
.progress-wrapper {
  position: relative;
  height: 4px;
  border-radius: var(--luml-radius-pill);
  overflow: hidden;
}
.progress-track {
  position: absolute;
  inset: 0;
  background: var(--luml-surface-100);
}
.progress-bar {
  position: absolute;
  top: 0;
  height: 4px;
  min-width: 2px;
  border-radius: var(--luml-radius-pill);
}
</style>
