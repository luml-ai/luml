import { computed, type Ref } from 'vue'
import type { AgentTask, Run } from '@/lib/api/data-agent/data-agent.interfaces'
import { type BoardColumn, type BoardItem, toBoardItem } from './board.types'

function hasPosition(item: BoardItem): boolean {
  return item.data.position != null
}

function sortItems(a: BoardItem, b: BoardItem): number {
  const aHas = hasPosition(a)
  const bHas = hasPosition(b)
  if (aHas && bHas) return a.data.position! - b.data.position!
  if (aHas && !bHas) return -1
  if (!aHas && bHas) return 1
  return new Date(b.data.updated_at).getTime() - new Date(a.data.updated_at).getTime()
}

export function useBoardItems(
  tasks: Ref<AgentTask[]>,
  runs: Ref<Run[]>,
  repositoryFilter?: Ref<string | null>,
) {
  const allItems = computed<BoardItem[]>(() => {
    const repoId = repositoryFilter?.value ?? null
    const filteredTasks = repoId != null
      ? tasks.value.filter((t) => t.repository_id === repoId)
      : tasks.value
    const filteredRuns = repoId != null
      ? runs.value.filter((r) => r.repository_id === repoId)
      : runs.value

    const items: BoardItem[] = [
      ...filteredTasks.map((t) => toBoardItem('task', t)),
      ...filteredRuns.map((r) => toBoardItem('run', r)),
    ]
    items.sort(sortItems)
    return items
  })

  const columns = computed<Record<BoardColumn, BoardItem[]>>(() => {
    const result: Record<BoardColumn, BoardItem[]> = {
      pending: [],
      running: [],
      completed: [],
      merged: [],
    }
    for (const item of allItems.value) {
      result[item.column].push(item)
    }
    return result
  })

  return { columns, allItems }
}
