<template>
  <div class="lane">
    <div class="lane-row" :class="{ 'lane-row--current': lane.current }">
      <button
        type="button"
        class="lane-select-button"
        :disabled="flowStore.isSwitchingBranch"
        @click="flowStore.switchBranch(lane.name)"
      ></button>
      <span class="lane-dot" :style="{ backgroundColor: dotColor }" />
      <div class="lane-body">
        <div class="lane-name">
          {{ lane.name }}
        </div>
        <div class="lane-meta">{{ lane.steps }} steps · {{ lane.updatedAgo }}</div>
      </div>
      <!--TODO: Add menu button
      <Button
        v-if="lane.current"
        severity="secondary"
        variant="text"
        class="lane-menu"
        aria-haspopup="menu"
      >
        <template #icon>
          <EllipsisVertical :size="16" />
        </template>
      </Button>-->
    </div>
    <div
      v-if="lane.children.length"
      class="lane-children"
      :style="{ '--lane-bridge-color': bridgeColor }"
    >
      <div
        v-for="(child, index) in lane.children"
        :key="child.id"
        class="lane-branch"
        :style="{
          '--lane-trunk-color': trunkColor(index),
          '--lane-branch-color': branchColor(index),
          '--lane-continue-color': continueColor(index),
        }"
      >
        <NotebooksLanesListItem :lane="child" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { INotebookLaneNode } from './interface'
import { computed } from 'vue'
import { useFlowStore } from '@/store/flow'
import NotebooksLanesListItem from './NotebooksLanesListItem.vue'

interface Props {
  lane: INotebookLaneNode
}

const props = defineProps<Props>()
const flowStore = useFlowStore()

function laneColor(isCurrentPath: boolean): string {
  return isCurrentPath ? 'var(--p-primary-color)' : 'var(--p-surface-300)'
}

function containsCurrent(lane: INotebookLaneNode): boolean {
  return lane.current || lane.children.some(containsCurrent)
}

const currentChildIndex = computed(() =>
  props.lane.children.findIndex((child) => containsCurrent(child)),
)

function trunkColor(index: number): string {
  return laneColor(currentChildIndex.value !== -1 && index <= currentChildIndex.value)
}

function branchColor(index: number): string {
  return laneColor(index === currentChildIndex.value)
}

function continueColor(index: number): string | undefined {
  const next = props.lane.children[index + 1]
  if (!next) return undefined
  return laneColor(currentChildIndex.value !== -1 && index < currentChildIndex.value)
}

const bridgeColor = computed(() => laneColor(currentChildIndex.value !== -1))

const dotColor = computed(() => laneColor(containsCurrent(props.lane)))
</script>

<style scoped>
@reference "@/assets/css/index.css";

.lane-row {
  @apply relative flex items-center gap-3 -mx-4 p-2 rounded-sm hover:text-primary;
}

.lane-select-button {
  @apply absolute left-0 top-0 w-full h-full cursor-pointer;
}

.lane-row--current {
  @apply bg-(--p-highlight-background);
}

.lane-dot {
  @apply w-2 h-2 rounded-full shrink-0 relative z-30;
}

.lane-body {
  @apply min-w-0 flex-1;
}

.lane-name {
  @apply text-sm truncate;
}

.lane-meta {
  @apply text-xs text-muted-color truncate;
}

.lane-menu {
  @apply shrink-0 px-2! ml-auto h-7;
}

.lane-children {
  @apply relative -ml-1;
}

.lane-children::before {
  content: '';
  position: absolute;
  z-index: 10;
  left: 0;
  top: -26px;
  height: 26px;
  width: 1px;
  background: var(--lane-bridge-color);
  transform: translateX(-50%);
}

.lane-branch {
  position: relative;
  padding-left: 8px;
}

.lane-branch:last-child {
  padding-bottom: 0;
}

.lane-branch::before {
  content: '';
  position: absolute;
  z-index: 20;
  left: -0.5px;
  top: 0;
  width: 5px;
  height: 25px;
  border-left: 1px solid var(--lane-trunk-color);
  border-bottom: 1px solid var(--lane-branch-color);
  border-bottom-left-radius: 4px;
}

.lane-branch:not(:last-child)::after {
  content: '';
  position: absolute;
  z-index: 10;
  left: -0.5px;
  top: 23px;
  bottom: 0;
  width: 1px;
  background: var(--lane-continue-color);
}
</style>
