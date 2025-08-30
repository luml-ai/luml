<template>
  <div class="content">
    <TraceItemsHeader
      v-model:open="opened"
      :items-count="evalsStore.spansCount || 0"
    ></TraceItemsHeader>
    <div class="list">
      <TraceSpan
        v-for="span in spansTree"
        :key="span.span_id"
        :data="span"
        :nesting="0"
        :selected-span-id="selectedSpanId"
        :all-opened="opened"
        @select="(payload) => $emit('select', payload)"
      ></TraceSpan>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TraceItemsHeader from './TraceItemsHeader.vue'
import TraceSpan from './TraceSpan.vue'
import type { TraceSpan as TraceSpanType } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { useEvalsStore } from '@/modules/experiment-snapshot/store/evals'

type Props = {
  spansTree: TraceSpanType[]
  selectedSpanId: string | undefined
}

type Emits = {
  select: [TraceSpanType]
}

defineEmits<Emits>()
defineProps<Props>()

const evalsStore = useEvalsStore()

const opened = ref(true)
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
  padding: 0 20px;
  flex: 1 1 auto;
  overflow-y: auto;
}
</style>
