<template>
  <Dialog
    v-model:visible="visible"
    modal
    block-scroll
    dismissable-mask
    :draggable="false"
    :style="dialogStyle"
    :pt="dialogPt"
    @show="load"
  >
    <template #header>
      <TraceDialogHeader :title="title" :event-id="eventId" />
    </template>
    <TraceLoader v-if="!trace && loading" />
    <div v-else-if="error" class="state">
      <MErrorState :error="error" @retry="load" />
    </div>
    <div v-else-if="emptyState" class="state">
      <MEmpty :title="emptyState.title" :detail="emptyState.detail" />
    </div>
    <div v-else-if="selectedSpan" class="content" :class="{ loading }" :aria-busy="loading">
      <TraceSpans
        :tree="tree"
        :count="spans.length"
        :range="range"
        :selected-span-id="selectedSpan.span_id"
        @select="selectSpan"
      />
      <TraceBody :span="selectedSpan" />
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { Dialog } from 'primevue'
import { api } from '@/api'
import type { TraceDetailResponse, TraceSpan } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { TRACE_DIALOG_GAP } from '@/constants/traces'
import { buildSpanTree, getSpanRange, getTraceDetailEmptyState } from '@/utils/traces'
import MEmpty from '@/components/MEmpty.vue'
import MErrorState from '@/components/MErrorState.vue'
import TraceDialogHeader from '@/components/traces/TraceDialogHeader.vue'
import TraceLoader from '@/components/traces/TraceLoader.vue'
import TraceSpans from '@/components/traces/TraceSpans.vue'
import TraceBody from '@/components/traces/TraceBody.vue'

interface Props {
  eventId: string | null
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible', { required: true })

const filtersStore = useFiltersStore()

const loaded = shallowRef<{ eventId: string; response: TraceDetailResponse } | null>(null)
const error = shallowRef<Error | null>(null)
const loading = ref(false)
const selection = shallowRef<{ eventId: string; spanId: string } | null>(null)

const dialogStyle = {
  width: `calc(100vw - ${2 * TRACE_DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * TRACE_DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}

const dialogPt = {
  mask: { style: { '--px-mask-background': 'transparent' } },
  header: { class: 'trace-dialog-header' },
  content: { class: 'trace-dialog-content' },
}

let requestId = 0

const response = computed(() =>
  loaded.value && loaded.value.eventId === props.eventId ? loaded.value.response : null,
)

const trace = computed(() => response.value?.trace ?? null)

const spans = computed(() => trace.value?.spans ?? [])

const tree = computed(() => buildSpanTree(spans.value))

const range = computed(() => getSpanRange(spans.value))

const emptyState = computed(() =>
  response.value ? getTraceDetailEmptyState(response.value) : null,
)

const selectedSpan = computed<TraceSpan | null>(() => {
  const current = selection.value
  const selected =
    current && current.eventId === props.eventId
      ? spans.value.find((span) => span.span_id === current.spanId)
      : undefined
  return selected ?? tree.value[0] ?? null
})

const title = computed(() => tree.value[0]?.name ?? 'Trace')

async function load() {
  const eventId = props.eventId
  if (!eventId) return
  const id = ++requestId
  loading.value = true
  try {
    const result = await api.monitoring.getTraceDetail(filtersStore.dimensions, eventId)
    if (id !== requestId) return
    loaded.value = { eventId, response: result }
    error.value = null
  } catch (e) {
    if (id !== requestId) return
    error.value = e instanceof Error ? e : new Error(String(e))
  } finally {
    if (id === requestId) loading.value = false
  }
}

watch(
  () => [filtersStore.dimensions, filtersStore.refreshKey],
  () => {
    if (visible.value) load()
  },
)

function selectSpan(span: TraceSpan) {
  if (!props.eventId) return
  selection.value = { eventId: props.eventId, spanId: span.span_id }
}
</script>

<style scoped>
.content {
  display: flex;
  height: 100%;
  min-height: 0;
  transition: opacity 0.2s;
}

.content.loading {
  opacity: 0.5;
  pointer-events: none;
}

.state {
  padding: 20px;
}
</style>

<style>
.trace-dialog-header {
  border-bottom: 1px solid var(--p-content-border-color);
  padding-top: 9px;
  padding-bottom: 9px;
}

.trace-dialog-content {
  flex: 1;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}
</style>
