<template>
  <div
    class="backdrop"
    data-testid="trace-detail-dialog"
    role="dialog"
    aria-modal="true"
    :aria-label="`Trace ${eventId}`"
    @click.self="$emit('close')"
  >
    <div class="dialog">
      <header class="head">
        <div class="titles">
          <h3 class="name">{{ rootSpan?.name ?? 'Inference call' }}</h3>
          <div class="facts">
            <span class="fact">Latency <b>{{ latency }}</b></span>
            <span class="fact">Spans <b>{{ spans.length }}</b></span>
            <span v-if="trace" class="fact">
              Status
              <b :class="statusClass">{{ trace.status }}</b>
            </span>
            <span class="fact mono id">{{ eventId }}</span>
          </div>
        </div>
        <button type="button" class="close" data-testid="trace-detail-close" @click="$emit('close')">
          <X :size="16" />
        </button>
      </header>

      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="3"
        error-title="Could not load this call"
        error-detail="It may have aged out of the selected window. Try widening the window."
        empty-title="Call not found"
        empty-detail="This call is no longer in the selected window."
      />

      <div v-else-if="selectedSpan" class="content">
        <TraceSpanTree
          :tree="tree"
          :selected-span-id="selectedSpan.span_id"
          :count="spans.length"
          :min-span-time="bounds.min"
          :max-span-time="bounds.max"
          @select="setSelectedSpan"
        />
        <TraceSpanBody :data="selectedSpan" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import type { TraceDetail, TraceSpanNode } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { buildSpanTree, getFormattedExecutionTime, spanTimeBounds } from '@/lib/spans'
import StateBlock from '@/components/StateBlock.vue'
import TraceSpanTree from '@/components/trace/TraceSpanTree.vue'
import TraceSpanBody from '@/components/trace/TraceSpanBody.vue'

const props = defineProps<{
  eventId: string
  trace: TraceDetail | null
  status: LoadStatus
}>()

const emit = defineEmits<{ close: [] }>()

const spans = computed(() => props.trace?.spans ?? [])
const tree = computed(() => buildSpanTree(spans.value))
const bounds = computed(() => spanTimeBounds(spans.value))
const rootSpan = computed(() => tree.value[0])

// The dialog only exists while a trace is open, so 'ready' means the payload arrived.
const view = computed(() => {
  if (props.status === 'idle' || props.status === 'loading') return 'loading'
  if (props.status === 'error') return 'error'
  return spans.value.length ? 'ready' : 'empty'
})

const selectedSpan = ref<TraceSpanNode | undefined>(undefined)

// The tree arrives after the fetch resolves; select the root as soon as it does.
watch(
  tree,
  (next) => {
    if (!next.length) return
    const stillThere = next.some((s) => s.span_id === selectedSpan.value?.span_id)
    if (!stillThere) selectedSpan.value = next[0]
  },
  { immediate: true },
)

function setSelectedSpan(span: TraceSpanNode): void {
  selectedSpan.value = span
}

const latency = computed(() => {
  if (bounds.value.max > bounds.value.min) {
    return getFormattedExecutionTime(bounds.value.max - bounds.value.min)
  }
  return props.trace ? `${Math.round(props.trace.latency_ms)}ms` : '—'
})

const statusClass = computed(() => {
  const code = props.trace?.status_code ?? 200
  return code >= 500 ? 'err' : code >= 400 ? 'warn' : 'ok'
})

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: stretch;
  justify-content: flex-end;
  background: rgb(0 0 0 / 45%);
}
.dialog {
  width: min(1100px, calc(100vw - 80px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--luml-border);
  background: var(--luml-bg);
}
.head {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--luml-space-4);
  padding: var(--luml-space-4) var(--luml-space-5);
  border-bottom: 1px solid var(--luml-border);
}
.name {
  margin: 0 0 6px;
  font-size: var(--luml-text-lg);
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--luml-space-4);
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.fact b {
  color: var(--luml-fg);
  font-weight: 500;
}
.fact b.ok {
  color: var(--luml-success-tint-fg);
}
.fact b.warn {
  color: var(--luml-warn-tint-fg);
}
.fact b.err {
  color: var(--luml-danger-tint-fg);
}
.id {
  word-break: break-all;
}
.close {
  flex-shrink: 0;
  display: inline-flex;
  padding: 5px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg-muted);
  cursor: pointer;
}
.close:hover {
  background: var(--luml-bg-hover);
}
.content {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;
  padding-top: var(--luml-space-4);
}
</style>
