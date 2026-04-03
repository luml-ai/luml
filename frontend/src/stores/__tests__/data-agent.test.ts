import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDataAgentStore } from '@/stores/data-agent'
import type { AgentTask, Run } from '@/lib/api/data-agent/data-agent.interfaces'

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
    fork_auto_approve: false,
    auto_mode: false,
    auto_terminate_timeout: 300,
    implement_timeout: 1800,
    run_timeout: 0,
    debug_timeout: 1800,
    fork_timeout: 900,
    primary_metric: 'metric',
    luml_collection_id: null,
    luml_organization_id: null,
    luml_orbit_id: null,
  },
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  ...overrides,
})

describe('data-agent store', () => {
  let store: ReturnType<typeof useDataAgentStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useDataAgentStore()
  })

  describe('task selection', () => {
    it('selectedTask is null initially', () => {
      expect(store.selectedTaskId).toBeNull()
      expect(store.selectedTask).toBeNull()
    })

    it('selectTask sets selectedTaskId and selectedTask computes correctly', () => {
      store.tasks = [makeTask({ id: 't1' }), makeTask({ id: 't2' })]
      store.selectTask('t2')
      expect(store.selectedTaskId).toBe('t2')
      expect(store.selectedTask?.id).toBe('t2')
    })

    it('selectTask(null) clears selection', () => {
      store.tasks = [makeTask({ id: 't1' })]
      store.selectTask('t1')
      expect(store.selectedTask).not.toBeNull()
      store.selectTask(null)
      expect(store.selectedTask).toBeNull()
    })

    it('selectedTask returns null if id not in tasks', () => {
      store.tasks = [makeTask({ id: 't1' })]
      store.selectTask('nonexistent')
      expect(store.selectedTask).toBeNull()
    })
  })

  describe('updateTask', () => {
    it('updates existing task in list', () => {
      store.tasks = [makeTask({ id: 't1', name: 'Old' })]
      store.updateTask(makeTask({ id: 't1', name: 'New' }))
      expect(store.tasks[0].name).toBe('New')
    })

    it('prepends task if not found in list', () => {
      store.tasks = [makeTask({ id: 't1' })]
      store.updateTask(makeTask({ id: 't2', name: 'Added' }))
      expect(store.tasks).toHaveLength(2)
      expect(store.tasks[0].id).toBe('t2')
    })
  })

  describe('removeTask', () => {
    it('removes task from list', () => {
      store.tasks = [makeTask({ id: 't1' }), makeTask({ id: 't2' })]
      store.removeTask('t1')
      expect(store.tasks).toHaveLength(1)
      expect(store.tasks[0].id).toBe('t2')
    })

    it('clears selection if removed task was selected', () => {
      store.tasks = [makeTask({ id: 't1' })]
      store.selectTask('t1')
      store.removeTask('t1')
      expect(store.selectedTaskId).toBeNull()
    })

    it('keeps selection if different task removed', () => {
      store.tasks = [makeTask({ id: 't1' }), makeTask({ id: 't2' })]
      store.selectTask('t1')
      store.removeTask('t2')
      expect(store.selectedTaskId).toBe('t1')
    })
  })

  describe('run management (existing)', () => {
    it('setRuns replaces runs list', () => {
      store.setRuns([makeRun({ id: 'r1' }), makeRun({ id: 'r2' })])
      expect(store.runs).toHaveLength(2)
    })

    it('selectRun sets selectedRunId', () => {
      store.setRuns([makeRun({ id: 'r1' })])
      store.selectRun('r1')
      expect(store.selectedRunId).toBe('r1')
      expect(store.selectedRun?.id).toBe('r1')
    })

    it('selectRun(null) clears graph state', () => {
      store.selectRun('r1')
      store.selectRun(null)
      expect(store.selectedRunId).toBeNull()
      expect(store.nodes).toEqual([])
      expect(store.edges).toEqual([])
    })

    it('removeRun clears selection if selected', () => {
      store.setRuns([makeRun({ id: 'r1' })])
      store.selectRun('r1')
      store.removeRun('r1')
      expect(store.selectedRunId).toBeNull()
      expect(store.runs).toHaveLength(0)
    })
  })
})
