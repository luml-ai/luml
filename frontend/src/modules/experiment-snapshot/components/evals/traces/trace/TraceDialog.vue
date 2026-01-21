<template>
  <Dialog v-model:visible="visible" :draggable="false" :pt="dialogPt" position="right" modal>
    <TraceSpans
      :tree="tree"
      :selected-span-id="selectedSpan.span_id"
      :count="count"
      :max-span-time="maxSpanTime"
      :min-span-time="minSpanTime"
      @select="setSelectedSpan"
    ></TraceSpans>
    <TraceBody class="body" :data="selectedSpan"></TraceBody>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Dialog } from 'primevue'
import TraceSpans from './TraceSpans.vue'
import TraceBody from './body/TraceBody.vue'
import type { TraceSpan } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { ref } from 'vue'

type Props = {
  tree: TraceSpan[]
  count: number
  maxSpanTime: number
  minSpanTime: number
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

const selectedSpan = ref<TraceSpan>(props.tree[0])

function setSelectedSpan(span: TraceSpan) {
  selectedSpan.value = span
}
</script>

<style scoped>
.models {
  flex: 1 1 auto;
  overflow-x: auto;
}
.body {
  flex: 1 1 auto;
  overflow: hidden;
}
</style>
