<template>
  <Dialog v-model:visible="visible" position="topright" :draggable="false" :pt="dialogPT">
    <template #header>
      <h2 class="dialog-title">
        <ListTree :size="16" />
        <span>Traces</span>
      </h2>
    </template>
    <div class="content">
      <div class="traces-list">
        <div v-for="trace in sortedTraces" :key="trace.traceId" class="trace-item">
          <button
            v-tooltip.left="trace.traceId"
            class="trace-item-name"
            @click="selectTrace(trace)"
          >
            {{ trace.traceId }}
          </button>
          <span class="trace-item-min-time">
            <span>{{ trace.minTime ? getTimeFromNs(trace.minTime) : '-' }}</span>
            <span>{{ trace.minTime ? getDateFromNs(trace.minTime) : '-' }}</span>
          </span>
          <span class="trace-item-count">
            <span>{{ trace.count }}</span>
            <span>spans</span>
          </span>
          <span class="trace-item-time">
            <span v-if="trace.minTime && trace.maxTime">
              {{ getFormattedTime(trace.minTime, trace.maxTime) }}
            </span>
            <span v-else>N/A</span>
            <Clock :size="16" color="var(--p-text-muted-color)" />
          </span>
        </div>
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import type { BaseTraceInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { Dialog, type DialogPassThroughOptions } from 'primevue'
import { Clock, ListTree } from 'lucide-vue-next'
import { getFormattedTime } from '@/modules/experiment-snapshot/helpers/helpers'
import { computed } from 'vue'

const dialogPT: DialogPassThroughOptions = {
  root: {
    style: 'margin-top: 80px; height: 86%; width: 550px',
  },
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

type Props = {
  data: BaseTraceInfo[]
}

type Emits = {
  select: [BaseTraceInfo]
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const visible = defineModel<boolean>('visible')

const sortedTraces = computed(() => {
  return props.data.sort((a, b) => {
    return (a.minTime || 0) - (b.minTime || 0)
  })
})

const getDateFromNs = computed(() => (ns: number) => {
  const ms = ns / 1_000_000
  return new Date(ms).toLocaleDateString()
})

const getTimeFromNs = computed(() => (ns: number) => {
  const ms = ns / 1_000_000
  return new Date(ms).toLocaleTimeString()
})

function selectTrace(trace: BaseTraceInfo) {
  emits('select', trace)
}
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.traces-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trace-item {
  font-size: 12px;
  display: grid;
  align-items: center;
  grid-template-columns: repeat(2, 2fr) repeat(2, 1fr);
  gap: 4px;
  padding: 4px 0;
}

.trace-item-name {
  text-align: left;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-primary-color);
  text-decoration: underline;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trace-item-count {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-item-min-time {
  color: var(--p-text-muted-color);
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
}

.trace-item-time {
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;

  &._center {
    justify-content: center;
    text-align: center;
  }
}
</style>
