<template>
  <div
    class="item"
    :class="{ selected: isSelected }"
    :style="{ paddingLeft: `${8 + 12 * nesting}px` }"
    @click="$emit('select', node)"
  >
    <button
      v-if="hasChildren"
      type="button"
      class="toggle"
      :aria-expanded="isOpened"
      :aria-label="isOpened ? `Collapse ${node.name}` : `Expand ${node.name}`"
      @click.stop="$emit('toggle', node.span_id)"
    >
      <component :is="isOpened ? ChevronDown : ChevronRight" :size="14" />
    </button>
    <div v-else class="toggle-placeholder" />
    <div class="body">
      <div class="title-row">
        <TraceSpanTitle class="title" :span="node" />
        <span
          v-if="isFailed"
          v-tooltip.top="'Span failed'"
          class="error-dot"
          role="img"
          aria-label="Span failed"
        />
      </div>
      <div class="progress">
        <div class="progress-offset" :style="{ width: `${bar.start}%` }" />
        <ProgressBar
          :value="bar.end"
          :show-value="false"
          class="progress-bar"
          :pt="{ value: { style: { background: spanType.color } } }"
        />
      </div>
    </div>
  </div>
  <template v-if="hasChildren && isOpened">
    <TraceSpanItem
      v-for="child in node.children"
      :key="child.span_id"
      :node="child"
      :nesting="nesting + 1"
      :range="range"
      :selected-span-id="selectedSpanId"
      :collapsed="collapsed"
      @select="$emit('select', $event)"
      @toggle="$emit('toggle', $event)"
    />
  </template>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ProgressBar } from 'primevue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import type { TraceSpan, TraceSpanNode } from '@/api/monitoring/interfaces'
import type { TraceSpanRange } from '@/types/traces'
import { getSpanBar, getSpanTypeData, isFailedSpan } from '@/utils/traces'
import TraceSpanTitle from '@/components/traces/TraceSpanTitle.vue'

interface Props {
  node: TraceSpanNode
  nesting: number
  range: TraceSpanRange
  selectedSpanId: string
  collapsed: ReadonlySet<string>
}

type Emits = {
  select: [TraceSpan]
  toggle: [string]
}

const props = defineProps<Props>()

defineEmits<Emits>()

const hasChildren = computed(() => props.node.children.length > 0)

const isOpened = computed(() => !props.collapsed.has(props.node.span_id))

const isSelected = computed(() => props.selectedSpanId === props.node.span_id)

const spanType = computed(() => getSpanTypeData(props.node.dfs_span_type))

const isFailed = computed(() => isFailedSpan(props.node))

const bar = computed(() => getSpanBar(props.node, props.range))
</script>

<style scoped>
.item {
  display: flex;
  flex-shrink: 0;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background-color 0.2s,
    box-shadow 0.2s;
}

.item.selected {
  border-color: var(--p-content-border-color);
  background: var(--p-content-background);
  box-shadow: var(--p-card-shadow);
  cursor: default;
}

.toggle,
.toggle-placeholder {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 24.5px;
  height: 24.5px;
}

.toggle {
  border-radius: var(--p-datatable-row-toggle-button-border-radius);
  color: var(--p-datatable-row-toggle-button-color);
  cursor: pointer;
  transition: background-color 0.2s;
}

.toggle:hover {
  background: var(--p-datatable-row-toggle-button-hover-background);
}

.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}

.title {
  flex: 1;
}

.error-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--p-message-error-color);
}

.progress {
  position: relative;
  overflow: hidden;
  border-radius: var(--p-progressbar-border-radius);
}

.progress-offset {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
  height: 4px;
  background: var(--p-progressbar-background);
}

.progress-bar {
  height: 4px;
}
</style>
