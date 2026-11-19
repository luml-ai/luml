<template>
  <div class="spans">
    <TraceSpansHeader :count="count" :expanded="expanded" @toggle="toggleAll" />
    <div class="list">
      <TraceSpanItem
        v-for="node in tree"
        :key="node.span_id"
        :node="node"
        :nesting="0"
        :range="range"
        :selected-span-id="selectedSpanId"
        :collapsed="collapsed"
        @select="$emit('select', $event)"
        @toggle="toggleSpan"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import type { TraceSpan, TraceSpanNode } from '@/api/monitoring/interfaces'
import type { TraceSpanRange } from '@/types/traces'
import { getCollapsibleSpanIds } from '@/utils/traces'
import TraceSpansHeader from '@/components/traces/TraceSpansHeader.vue'
import TraceSpanItem from '@/components/traces/TraceSpanItem.vue'

interface Props {
  tree: TraceSpanNode[]
  count: number
  range: TraceSpanRange
  selectedSpanId: string
}

type Emits = {
  select: [TraceSpan]
}

const props = defineProps<Props>()

defineEmits<Emits>()

const collapsed = shallowRef<ReadonlySet<string>>(new Set())

const collapsibleIds = computed(() => getCollapsibleSpanIds(props.tree))

const expanded = computed(() => collapsibleIds.value.some((id) => !collapsed.value.has(id)))

function toggleAll() {
  collapsed.value = expanded.value ? new Set(collapsibleIds.value) : new Set()
}

function toggleSpan(spanId: string) {
  const next = new Set(collapsed.value)
  if (next.has(spanId)) next.delete(spanId)
  else next.add(spanId)
  collapsed.value = next
}
</script>

<style scoped>
.spans {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 320px;
  flex-shrink: 0;
  padding: 20px 0;
  overflow: hidden;
  border-right: 1px solid var(--p-divider-border-color);
}

.list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  padding: 0 20px;
  overflow-y: auto;
}
</style>
