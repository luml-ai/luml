<template>
  <div class="lanes-list">
    <NotebooksLanesListItem v-for="lane in tree" :key="lane.id" :lane="lane" />
  </div>
</template>

<script setup lang="ts">
import type { INotebookLane, INotebookLaneNode } from './interface'
import NotebooksLanesListItem from './NotebooksLanesListItem.vue'

const MOCK_LANES: INotebookLane[] = [
  { id: '1', name: 'Test-1', steps: 72, updatedAgo: '1h ago', parentId: null, state: 'active' },
  { id: '2', name: 'Test-2', steps: 25, updatedAgo: '1h ago', parentId: '1', state: 'active' },
  { id: '3', name: 'Test-3', steps: 4, updatedAgo: '1h ago', parentId: '2', state: 'active' },
  {
    id: '3-1',
    name: 'Test-3-1',
    steps: 4,
    updatedAgo: '2h ago',
    parentId: '3',
    state: 'active',
  },
  {
    id: '3-2',
    name: 'Test-3-2',
    steps: 2,
    updatedAgo: '2h ago',
    parentId: '3',
    state: 'inactive',
  },
  {
    id: '3-1-1',
    name: 'Test-3-1-1',
    steps: 4,
    updatedAgo: '3h ago',
    parentId: '3-1',
    state: 'active',
    current: true,
  },
  {
    id: '3-1-2',
    name: 'Test-3-1-2',
    steps: 1,
    updatedAgo: '3h ago',
    parentId: '3-1',
    state: 'inactive',
  },
  {
    id: '3-1-1-1',
    name: 'Test-3-1-1-1',
    steps: 6,
    updatedAgo: '3h ago',
    parentId: '3-1-1',
    state: 'active',
  },
  {
    id: '3-2-1',
    name: 'Test-3-2-1',
    steps: 3,
    updatedAgo: '2h ago',
    parentId: '3-2',
    state: 'inactive',
  },
  {
    id: '2-1',
    name: 'Test-2-1',
    steps: 8,
    updatedAgo: '1h ago',
    parentId: '2',
    state: 'inactive',
  },
  { id: '4', name: 'Test-4', steps: 61, updatedAgo: '1h ago', parentId: '1', state: 'active' },
  {
    id: '4-1',
    name: 'Test-4-1',
    steps: 15,
    updatedAgo: '1h ago',
    parentId: '4',
    state: 'inactive',
  },
  { id: '5', name: 'Test-5', steps: 9, updatedAgo: '1h ago', parentId: '1', state: 'inactive' },
  { id: '6', name: 'Test-6', steps: 33, updatedAgo: '1h ago', parentId: '1', state: 'active' },
  {
    id: '6-1',
    name: 'Test-6-1',
    steps: 7,
    updatedAgo: '2h ago',
    parentId: '6',
    state: 'active',
  },
  {
    id: '6-2',
    name: 'Test-6-2',
    steps: 12,
    updatedAgo: '2h ago',
    parentId: '6',
    state: 'active',
  },
  {
    id: '6-3',
    name: 'Test-6-3',
    steps: 5,
    updatedAgo: '2h ago',
    parentId: '6',
    state: 'inactive',
  },
  {
    id: '6-2-1',
    name: 'Test-6-2-1',
    steps: 2,
    updatedAgo: '3h ago',
    parentId: '6-2',
    state: 'inactive',
  },
  { id: '7', name: 'Test-7', steps: 19, updatedAgo: '1h ago', parentId: '1', state: 'active' },
  {
    id: '7-1',
    name: 'Test-7-1',
    steps: 3,
    updatedAgo: '2h ago',
    parentId: '7',
    state: 'inactive',
  },
]

function buildLaneTree(lanes: INotebookLane[]): INotebookLaneNode[] {
  const nodes = new Map<string, INotebookLaneNode>(
    lanes.map((lane) => [lane.id, { ...lane, children: [] }]),
  )
  const roots: INotebookLaneNode[] = []

  for (const lane of lanes) {
    const node = nodes.get(lane.id)
    if (!node) continue
    const parent = lane.parentId ? nodes.get(lane.parentId) : undefined
    if (parent) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}

const tree = buildLaneTree(MOCK_LANES)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.lanes-list {
  @apply flex flex-col px-4 pb-2 max-h-72.5 overflow-y-auto;
}
</style>
