<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, inject, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useConfirm } from 'primevue'
import { api } from '@/lib/api'
import { useDataAgentStore } from '@/stores/data-agent'
import { useBoardItems } from '@/components/data-agent/board/useBoardItems'
import { COLUMN_DEFS, FAIL_STATUSES, type BoardColumn as BoardCol, type BoardItem } from '@/components/data-agent/board/board.types'
import type { AgentTask, Run } from '@/lib/api/data-agent/data-agent.interfaces'
import BoardToolbar from '@/components/data-agent/board/BoardToolbar.vue'
import BoardColumn from '@/components/data-agent/board/BoardColumn.vue'

const store = useDataAgentStore()
const router = useRouter()
const confirm = useConfirm()

const tasks = ref<AgentTask[]>([])
const runs = ref<Run[]>([])
const repositoryFilter = ref<string | null>(null)

const { columns } = useBoardItems(tasks, runs, repositoryFilter)

const failCounts = computed(() => {
  const counts = {} as Record<BoardCol, number>
  for (const col of COLUMN_DEFS) {
    counts[col.key] = (columns.value[col.key] ?? []).filter(
      (item) => FAIL_STATUSES.has(item.data.status),
    ).length
  }
  return counts
})

const newItemType = inject<Ref<string | null>>('newItemType')!
const boardRefreshTrigger = inject<Ref<number>>('boardRefreshTrigger')!

watch(boardRefreshTrigger, () => refresh())

function openCreate() {
  newItemType.value = 'task'
}

let refreshInterval: ReturnType<typeof setInterval> | null = null

async function refresh() {
  const repoId = repositoryFilter.value ?? undefined
  const [taskList, runList, repoList] = await Promise.all([
    api.dataAgent.listTasks(repoId),
    api.dataAgent.listRuns(repoId),
    api.dataAgent.listRepositories(),
  ])
  tasks.value = taskList
  runs.value = runList
  store.tasks = taskList
  store.setRuns(runList)
  store.repositories = repoList
}

function onSelect(item: BoardItem) {
  if (item.kind === 'task') {
    router.push({ name: 'data-agent-task', params: { taskId: item.data.id } })
  } else {
    router.push({ name: 'data-agent-run', params: { runId: item.data.id } })
  }
}

async function onStart(item: BoardItem) {
  if (item.kind === 'run') {
    await api.dataAgent.startRun(item.data.id)
  } else {
    await api.dataAgent.openTerminal(item.data.id)
  }
  await refresh()
}

async function onResume(item: BoardItem) {
  if (item.kind !== 'task') return
  await api.dataAgent.openTerminal(item.data.id)
  await refresh()
}

function onDelete(item: BoardItem) {
  const label = item.kind === 'task' ? 'task' : 'workflow'
  confirm.require({
    header: `Delete this ${label}?`,
    message: `This will permanently delete the ${label} "${item.data.name}". This action cannot be undone.`,
    acceptProps: {
      label: 'Delete',
      severity: 'danger',
    },
    rejectProps: {
      label: 'Cancel',
      outlined: true,
    },
    accept: async () => {
      if (item.kind === 'task') {
        await api.dataAgent.deleteTask(item.data.id)
      } else {
        await api.dataAgent.deleteRun(item.data.id)
      }
      await refresh()
    },
  })
}

async function onReorder(orderedItems: BoardItem[]) {
  const taskPositions: { id: string; position: number }[] = []
  const runPositions: { id: string; position: number }[] = []

  orderedItems.forEach((item, index) => {
    if (item.kind === 'task') {
      taskPositions.push({ id: item.data.id, position: index })
    } else {
      runPositions.push({ id: item.data.id, position: index })
    }
  })

  // Optimistic update
  for (const tp of taskPositions) {
    const task = tasks.value.find((t) => t.id === tp.id)
    if (task) task.position = tp.position
  }
  for (const rp of runPositions) {
    const run = runs.value.find((r) => r.id === rp.id)
    if (run) run.position = rp.position
  }

  try {
    const promises: Promise<void>[] = []
    if (taskPositions.length > 0) promises.push(api.dataAgent.reorderTasks(taskPositions))
    if (runPositions.length > 0) promises.push(api.dataAgent.reorderRuns(runPositions))
    await Promise.all(promises)
  } catch {
    await refresh()
  }
}

onMounted(() => {
  refresh()
  refreshInterval = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="board-view">
    <BoardToolbar
      :repositories="store.repositories"
      :repository-filter="repositoryFilter"
      @update:repository-filter="repositoryFilter = $event"
    />
    <div class="board-columns">
      <BoardColumn
        v-for="col in COLUMN_DEFS"
        :key="col.key"
        :title="col.label"
        :severity="col.severity"
        :items="columns[col.key]"
        :fail-count="failCounts[col.key]"
        :repositories="store.repositories"
        :show-create="col.key === 'pending'"
        @select="onSelect"
        @start="onStart"
        @resume="onResume"
        @delete="onDelete"
        @create="openCreate"
        @reorder="onReorder"
      />
    </div>
  </div>
</template>

<style scoped>
.board-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 12px;
  overflow: hidden;
  padding-top: 12px;
}

.board-columns {
  display: flex;
  gap: 12px;
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
