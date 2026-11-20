<template>
  <Dialog
    v-model:visible="visible"
    :draggable="false"
    :pt="dialogPt"
    :close-on-escape="openViewers === 0"
    position="right"
    modal
  >
    <TraceSpans
      :tree="tree"
      :selected-span-id="selectedSpan.span_id"
      :count="count"
      :max-span-time="maxSpanTime"
      :min-span-time="minSpanTime"
      @select="setSelectedSpan"
    ></TraceSpans>
    <TraceBody
      ref="body"
      :data="selectedSpan"
      :artifact-id="artifactId"
      :trace-id="traceId"
    ></TraceBody>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { TraceSpan } from '@/interfaces/interfaces'
import { ref, useTemplateRef } from 'vue'
import { Dialog } from 'primevue'
import TraceSpans from './TraceSpans.vue'
import TraceBody from './body/TraceBody.vue'
import { provideNestedViewers } from '../../../ui/nestedViewer'

type Props = {
  tree: TraceSpan[]
  count: number
  maxSpanTime: number | null
  minSpanTime: number | null
  artifactId: string
  traceId: string
}

const props = defineProps<Props>()

const dialogPt: DialogPassThroughOptions = {
  mask: {
    style: 'align-items: flex-start; padding: 64px 0 56px;',
  },
  root: {
    style: 'width: calc(100vw - 140px); height: 100%; max-height: none;',
  },
  header: {
    style: 'padding: 16px 20px; justify-content: flex-end;',
  },
  content: {
    style: 'display: flex; padding: 0; overflow: hidden;',
  },
  pcCloseButton: {},
}

const visible = defineModel<boolean>('visible')
const openViewers = provideNestedViewers()

const selectedSpan = ref<TraceSpan>(props.tree[0] as TraceSpan)

const body = useTemplateRef('body')

// Selecting the same span again does not change the selection, so it retries a failed load.
function setSelectedSpan(span: TraceSpan) {
  if (span.span_id === selectedSpan.value.span_id) body.value?.retryFailedPayload()
  selectedSpan.value = span
}
</script>

<style scoped>
.models {
  flex: 1 1 auto;
  overflow-x: auto;
}
</style>
