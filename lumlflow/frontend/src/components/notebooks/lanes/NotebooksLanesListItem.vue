<template>
  <div class="lane">
    <div class="lane-row" :class="{ 'lane-row--current': lane.current }">
      <button
        type="button"
        class="lane-select-button"
        :disabled="flowStore.isSwitchingBranch"
        @click="onSelect"
      >
        <span class="lane-dot" :style="{ backgroundColor: dotColor }" />
        <span class="lane-body">
          <span class="lane-name" v-overflow-tooltip.top="lane.name">{{ lane.name }}</span>
          <span class="lane-meta">
            <template v-if="lane.stepsLabel">{{ lane.stepsLabel }} · </template>
            {{ lane.updatedAgo }}
          </span>
        </span>
      </button>
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
import { useDiscardConfirm } from '@/composables/useDiscardConfirm'
import NotebooksLanesListItem from './NotebooksLanesListItem.vue'

interface Props {
  lane: INotebookLaneNode
}

const props = defineProps<Props>()
const flowStore = useFlowStore()
const { confirmLeave } = useDiscardConfirm()

async function onSelect() {
  if (props.lane.current) return
  if (!(await confirmLeave())) return
  void flowStore.switchBranch(props.lane.name)
}

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
  @apply -mx-4 rounded-sm hover:text-primary;
}

.lane-select-button {
  @apply flex items-center gap-3 w-full p-2 text-left cursor-pointer;
}

.lane-row--current {
  @apply bg-(--p-highlight-background);
}

.lane-dot {
  @apply w-2 h-2 rounded-full shrink-0 relative z-30;
}

.lane-body {
  @apply block min-w-0 flex-1;
}

.lane-name {
  @apply block text-sm truncate;
}

.lane-meta {
  @apply block text-xs text-muted-color truncate;
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
