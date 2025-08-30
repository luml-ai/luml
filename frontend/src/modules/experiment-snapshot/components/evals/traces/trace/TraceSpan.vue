<template>
  <div
    class="item"
    :style="{
      paddingLeft: 8 + 12 * nesting + 'px',
    }"
    :class="{
      selected: selectedSpanId === data.span_id,
    }"
    @click="$emit('select', data)"
  >
    <Button
      v-if="data.children.length"
      class="button"
      severity="secondary"
      variant="text"
      size="small"
      @click.stop="spanOpened = !spanOpened"
    >
      <template #icon>
        <component :is="spanOpened ? ChevronDown : ChevronRight" :size="14"></component>
      </template>
    </Button>
    <div v-else style="width: 35px; flex: 0 0 auto"></div>
    <div class="item-body">
      <h4 class="title">
        <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" />
        <span>{{ data.name }}</span>
      </h4>
      <div class="info">
        <History :size="12" />
        <span>{{ time }}</span>
      </div>
      <div class="progress-wrapper">
        <div
          class="progress-plug"
          :style="{
            width: startProgress + '%',
          }"
        ></div>
        <ProgressBar
          :value="value"
          :show-value="false"
          class="progress"
          :pt="{
            value: {
              style: {
                backgroundColor: spanTypeData.color,
              },
            },
          }"
        ></ProgressBar>
      </div>
    </div>
  </div>
  <div v-if="data.children.length && spanOpened" class="children">
    <TraceSpan
      v-for="item in data.children"
      :key="item.span_id"
      :data="item"
      :nesting="nesting + 1"
      :selected-span-id="selectedSpanId"
      :all-opened="allOpened"
      @select="(payload) => $emit('select', payload)"
    ></TraceSpan>
  </div>
</template>

<script setup lang="ts">
import type { TraceSpan as TraceSpanType } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { Button, ProgressBar } from 'primevue'
import { ChevronDown, ChevronRight, History } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useEvalsStore } from '@/modules/experiment-snapshot/store/evals'
import { getFormattedTime, getSpanTypeData } from '@/modules/experiment-snapshot/helpers/helpers'

type Props = {
  data: TraceSpanType
  nesting: number
  selectedSpanId: string | undefined
  allOpened: boolean
}

type Emits = {
  select: [TraceSpanType]
}

defineEmits<Emits>()
const props = defineProps<Props>()

const evalsStore = useEvalsStore()

const spanOpened = ref(true)

const value = computed(() => 100)

const spanTypeData = computed(() => {
  return getSpanTypeData(props.data.dfs_span_type)
})

const time = computed(() => {
  return getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano)
})

const startProgress = computed(() => {
  if (!evalsStore.minSpanTime || !evalsStore.maxSpanTime) return 0
  const result =
    (props.data.start_time_unix_nano - evalsStore.minSpanTime) /
    (evalsStore.maxSpanTime - evalsStore.minSpanTime)
  return result * 100
})

const endProgress = computed(() => {
  if (!evalsStore.minSpanTime || !evalsStore.maxSpanTime) return 0
  const result =
    (props.data.end_time_unix_nano - evalsStore.minSpanTime) /
    (evalsStore.maxSpanTime - evalsStore.minSpanTime)
  return result * 100
})

watch(
  () => props.allOpened,
  (val) => {
    spanOpened.value = val
  },
)
</script>

<style scoped>
.item {
  padding: 8px;
  border-radius: 8px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  overflow: hidden;
  margin-bottom: 4px;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background-color 0.2s,
    box-shadow 0.2s;
}
.item.selected {
  border-color: var(--p-content-border-color);
  background: var(--p-content-background);
  box-shadow: var(--card-shadow);
  cursor: default;
}
.button {
  flex: 0 0 auto;
}
.item-body {
  flex: 1 1 auto;
}
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.info {
  padding-left: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
  margin-bottom: 8px;
}
.progress {
  height: 4px;
}
.progress-wrapper {
  position: relative;
  border-radius: var(--p-progressbar-border-radius);
  overflow: hidden;
}

.progress-plug {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  height: 4px;
  background: var(--p-progressbar-background);
}
</style>
