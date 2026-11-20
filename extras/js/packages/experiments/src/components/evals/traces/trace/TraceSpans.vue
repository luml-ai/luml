<template>
  <div class="content">
    <TraceItemsHeader v-model:open="opened" :items-count="count"></TraceItemsHeader>
    <div class="list">
      <VirtualScroller
        :items="rows"
        :item-size="TRACE_ROW_HEIGHT"
        :pt="{ content: { style: 'width: 100%' } }"
        class="scroller"
      >
        <template #item="{ item }">
          <div :key="item.span.span_id" class="row">
            <TraceSpan
              :data="item.span"
              :nesting="item.depth"
              :opened="item.opened"
              :selected-span-id="selectedSpanId"
              :max-span-time="maxSpanTime"
              :min-span-time="minSpanTime"
              @select="(payload: TraceSpanType) => $emit('select', payload)"
              @toggle="toggle"
            ></TraceSpan>
          </div>
        </template>
      </VirtualScroller>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TraceSpan as TraceSpanType } from '@/interfaces/interfaces'
import { computed, ref, shallowRef, watch } from 'vue'
import { VirtualScroller } from 'primevue'
import { flattenTraceTree, spansWithChildren } from './traceRows'
import TraceItemsHeader from './TraceItemsHeader.vue'
import TraceSpan from './TraceSpan.vue'

type Props = {
  tree: TraceSpanType[]
  selectedSpanId: string | undefined
  count: number
  maxSpanTime: number | null
  minSpanTime: number | null
}

type Emits = {
  select: [TraceSpanType]
}

defineEmits<Emits>()
const props = defineProps<Props>()

// Includes the 4px gap below each span.
const TRACE_ROW_HEIGHT = 67
const rowHeight = `${TRACE_ROW_HEIGHT}px`

const opened = ref(true)
const collapsed = shallowRef<ReadonlySet<string>>(new Set())

const rows = computed(() => flattenTraceTree(props.tree, collapsed.value))

// Opening a span opens its whole subtree, as the recursive tree did when it mounted
// the children again.
function toggle(span: TraceSpanType) {
  const next = new Set(collapsed.value)
  if (next.has(span.span_id)) {
    next.delete(span.span_id)
    spansWithChildren(span.children).forEach((spanId) => next.delete(spanId))
  } else {
    next.add(span.span_id)
  }
  collapsed.value = next
}

watch(opened, (value) => {
  collapsed.value = value ? new Set() : new Set(spansWithChildren(props.tree))
})
</script>

<style scoped>
.content {
  width: 400px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  padding-bottom: 20px;
  overflow: hidden;
  border-right: 1px solid var(--p-divider-border-color);
}
.list {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
}
.scroller {
  position: absolute;
  inset: 0;
}
.row {
  height: v-bind(rowHeight);
  box-sizing: border-box;
  padding: 0 20px 4px;
}
</style>
