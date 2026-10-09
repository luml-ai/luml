<template>
  <div class="tree">
    <header class="head">
      <p class="label">{{ count }} {{ count === 1 ? 'span' : 'spans' }}</p>
      <button type="button" class="toggle-all" data-testid="trace-toggle-all" @click="opened = !opened">
        {{ opened ? 'Collapse all' : 'Expand all' }}
      </button>
    </header>

    <div class="list">
      <TraceSpanItem
        v-for="span in tree"
        :key="span.span_id"
        :data="span"
        :nesting="0"
        :selected-span-id="selectedSpanId"
        :all-opened="opened"
        :min-span-time="minSpanTime"
        :max-span-time="maxSpanTime"
        @select="(payload: TraceSpanNode) => $emit('select', payload)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { TraceSpanNode } from '@/api/types'
import TraceSpanItem from './TraceSpanItem.vue'

defineProps<{
  tree: TraceSpanNode[]
  selectedSpanId: string | undefined
  count: number
  minSpanTime: number
  maxSpanTime: number
}>()

defineEmits<{ select: [TraceSpanNode] }>()

const opened = ref(true)
</script>

<style scoped>
.tree {
  width: 340px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--luml-border);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px 10px;
}
.label {
  margin: 0;
  font-size: 11px;
  color: var(--luml-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.toggle-all {
  border: none;
  background: transparent;
  color: var(--luml-fg-muted);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.toggle-all:hover {
  color: var(--luml-fg);
}
.list {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 0 8px 8px;
}
</style>
