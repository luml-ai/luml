import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useBoardItems } from '../useBoardItems'
import type { AgentTask, Run } from '@/lib/api/prisma/prisma.interfaces'

const makeTask = (overrides: Partial<AgentTask> = {}): AgentTask => ({
  id: 'task1',
  repository_id: 'repo10',
  name: 'Task',
  branch: 'b',
  worktree_path: '/wt',
  agent_id: 'a',
  status: 'pending',
  prompt: '',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  ...overrides,
})

const makeRun = (overrides: Partial<Run> = {}): Run => ({
  id: 'run1',
  repository_id: 'repo10',
  name: 'Run',
  objective: '',
  status: 'pending',
  config: {
    max_depth: 3,
    max_children_per_fork: 2,
    max_debug_retries: 1,
    max_concurrency: 1,
    run_command_template: '',
    agent_id: 'a',
    auto_mode: false,
    auto_terminate_timeout: 300,
  },
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  ...overrides,
})

describe('useBoardItems', () => {
  it('groups items into correct columns', () => {
    const tasks = ref([
      makeTask({ id: 't1', status: 'pending' }),
      makeTask({ id: 't2', status: 'succeeded' }),
      makeTask({ id: 't3', status: 'failed' }),
    ])
    const runs = ref([
      makeRun({ id: 'r10', status: 'running' }),
      makeRun({ id: 'r11', status: 'succeeded' }),
      makeRun({ id: 'r12', status: 'failed' }),
    ])

    const { columns } = useBoardItems(tasks, runs)

    expect(columns.value.pending).toHaveLength(1)
    expect(columns.value.running).toHaveLength(1)
    expect(columns.value.completed).toHaveLength(4)
    expect(columns.value.merged).toHaveLength(0)
  })

  it('sorts items by updated_at descending', () => {
    const tasks = ref([
      makeTask({ id: 't1', updated_at: '2025-01-01T00:00:00Z' }),
      makeTask({ id: 't2', updated_at: '2025-01-03T00:00:00Z' }),
    ])
    const runs = ref([makeRun({ id: 'r10', updated_at: '2025-01-02T00:00:00Z' })])

    const { allItems } = useBoardItems(tasks, runs)

    expect(allItems.value[0].data.id).toBe('t2')
    expect(allItems.value[1].data.id).toBe('r10')
    expect(allItems.value[2].data.id).toBe('t1')
  })

  it('filters by repository when filter is provided', () => {
    const tasks = ref([
      makeTask({ id: 't1', repository_id: 'repo10' }),
      makeTask({ id: 't2', repository_id: 'repo20' }),
    ])
    const runs = ref([
      makeRun({ id: 'r10', repository_id: 'repo10' }),
      makeRun({ id: 'r11', repository_id: 'repo20' }),
    ])
    const filter = ref<string | null>('repo10')

    const { allItems } = useBoardItems(tasks, runs, filter)

    expect(allItems.value).toHaveLength(2)
    expect(allItems.value.every((i) => i.data.repository_id === 'repo10')).toBe(true)
  })

  it('shows all items when filter is null', () => {
    const tasks = ref([
      makeTask({ id: 't1', repository_id: 'repo10' }),
      makeTask({ id: 't2', repository_id: 'repo20' }),
    ])
    const runs = ref([makeRun({ id: 'r10', repository_id: 'repo10' })])
    const filter = ref<string | null>(null)

    const { allItems } = useBoardItems(tasks, runs, filter)

    expect(allItems.value).toHaveLength(3)
  })

  it('returns empty columns when no data', () => {
    const tasks = ref<AgentTask[]>([])
    const runs = ref<Run[]>([])

    const { columns } = useBoardItems(tasks, runs)

    expect(columns.value.pending).toHaveLength(0)
    expect(columns.value.running).toHaveLength(0)
    expect(columns.value.completed).toHaveLength(0)
    expect(columns.value.merged).toHaveLength(0)
  })

  it('places merged tasks in merged column', () => {
    const tasks = ref([
      makeTask({ id: 't1', status: 'merged' }),
      makeTask({ id: 't2', status: 'succeeded' }),
    ])
    const runs = ref<Run[]>([])

    const { columns } = useBoardItems(tasks, runs)

    expect(columns.value.merged).toHaveLength(1)
    expect(columns.value.merged[0].data.id).toBe('t1')
    expect(columns.value.completed).toHaveLength(1)
  })

  it('reacts to ref changes', () => {
    const tasks = ref<AgentTask[]>([])
    const runs = ref<Run[]>([])

    const { allItems } = useBoardItems(tasks, runs)
    expect(allItems.value).toHaveLength(0)

    tasks.value = [makeTask({ id: 't1' })]
    expect(allItems.value).toHaveLength(1)

    runs.value = [makeRun({ id: 'r10' })]
    expect(allItems.value).toHaveLength(2)
  })
})
