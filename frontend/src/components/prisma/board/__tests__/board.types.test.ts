import { describe, it, expect } from 'vitest'
import {
  COLUMN_DEFS,
  STATUS_TO_COLUMN,
  FAIL_STATUSES,
  toBoardItem,
  statusSeverity,
  type BoardColumn,
} from '../board.types'
import type { AgentTask, Run } from '@/lib/api/prisma/prisma.interfaces'

const baseTask: AgentTask = {
  id: 'task1',
  repository_id: 'repo10',
  name: 'Test Task',
  branch: 'feature-1',
  worktree_path: '/tmp/wt',
  agent_id: 'claude',
  status: 'pending',
  prompt: 'do stuff',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const baseRun: Run = {
  id: 'run2',
  repository_id: 'repo10',
  name: 'Test Run',
  objective: 'run something',
  status: 'pending',
  config: {
    max_depth: 3,
    max_children_per_fork: 2,
    max_debug_retries: 1,
    max_concurrency: 1,
    run_command_template: '',
    agent_id: 'claude',
    auto_mode: false,
    auto_terminate_timeout: 300,
  },
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('COLUMN_DEFS', () => {
  it('defines exactly 4 columns in order', () => {
    expect(COLUMN_DEFS).toHaveLength(4)
    expect(COLUMN_DEFS.map((c) => c.key)).toEqual(['pending', 'running', 'completed', 'merged'])
  })
})

describe('STATUS_TO_COLUMN', () => {
  it('maps all statuses to board columns', () => {
    const expected: Record<string, BoardColumn> = {
      pending: 'pending',
      running: 'running',
      succeeded: 'completed',
      failed: 'completed',
      canceled: 'completed',
      merged: 'merged',
      archived: 'completed',
    }
    expect(STATUS_TO_COLUMN).toEqual(expected)
  })
})

describe('toBoardItem', () => {
  it('creates a task board item with correct column', () => {
    const item = toBoardItem('task', { ...baseTask, status: 'succeeded' })
    expect(item.kind).toBe('task')
    expect(item.column).toBe('completed')
    expect(item.data.name).toBe('Test Task')
  })

  it('defaults to pending for unknown task status', () => {
    const item = toBoardItem('task', { ...baseTask, status: 'unknown_status' })
    expect(item.column).toBe('pending')
  })

  it('maps failed status to completed column', () => {
    const item = toBoardItem('task', { ...baseTask, status: 'failed' })
    expect(item.column).toBe('completed')
  })

  it('maps merged status to merged column', () => {
    const item = toBoardItem('task', { ...baseTask, status: 'merged' })
    expect(item.column).toBe('merged')
  })

  it('creates a run board item with correct column', () => {
    const item = toBoardItem('run', { ...baseRun, status: 'succeeded' })
    expect(item.kind).toBe('run')
    expect(item.column).toBe('completed')
    expect(item.data.name).toBe('Test Run')
  })

  it('maps canceled to completed column', () => {
    const item = toBoardItem('run', { ...baseRun, status: 'canceled' })
    expect(item.column).toBe('completed')
  })

  it('defaults to pending for unknown run status', () => {
    const item = toBoardItem('run', { ...baseRun, status: 'weird' })
    expect(item.column).toBe('pending')
  })
})

describe('FAIL_STATUSES', () => {
  it('contains failed and canceled', () => {
    expect(FAIL_STATUSES).toEqual(new Set(['failed', 'canceled']))
  })

  it('does not contain success statuses', () => {
    expect(FAIL_STATUSES.has('succeeded')).toBe(false)
    expect(FAIL_STATUSES.has('merged')).toBe(false)
  })
})

describe('statusSeverity', () => {
  it('returns correct severity for known statuses', () => {
    expect(statusSeverity('pending')).toBe('warn')
    expect(statusSeverity('running')).toBe('info')
    expect(statusSeverity('succeeded')).toBe('success')
    expect(statusSeverity('failed')).toBe('danger')
    expect(statusSeverity('canceled')).toBe('secondary')
    expect(statusSeverity('merged')).toBe('success')
    expect(statusSeverity('archived')).toBe('secondary')
  })

  it('returns secondary for unknown statuses', () => {
    expect(statusSeverity('unknown')).toBe('secondary')
  })
})
