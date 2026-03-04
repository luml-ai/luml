import type { AgentTask, Run } from '@/lib/api/data-agent/data-agent.interfaces'

export type BoardColumn = 'pending' | 'running' | 'completed' | 'merged'

export interface ColumnDef {
  key: BoardColumn
  label: string
  severity: 'warn' | 'info' | 'success' | 'danger'
  icon: string
}

export const COLUMN_DEFS: ColumnDef[] = [
  { key: 'pending', label: 'Pending', severity: 'warn', icon: 'clock' },
  { key: 'running', label: 'Running', severity: 'info', icon: 'loader' },
  { key: 'completed', label: 'Completed', severity: 'success', icon: 'check-circle' },
  { key: 'merged', label: 'Merged', severity: 'info', icon: 'git-merge' },
]

export const STATUS_TO_COLUMN: Record<string, BoardColumn> = {
  pending: 'pending',
  running: 'running',
  succeeded: 'completed',
  failed: 'completed',
  canceled: 'completed',
  merged: 'merged',
  archived: 'completed',
}

export const FAIL_STATUSES = new Set(['failed', 'canceled'])

export type BoardItem =
  | { kind: 'task'; column: BoardColumn; data: AgentTask }
  | { kind: 'run'; column: BoardColumn; data: Run }

export function toBoardItem(kind: 'task', data: AgentTask): BoardItem
export function toBoardItem(kind: 'run', data: Run): BoardItem
export function toBoardItem(kind: 'task' | 'run', data: AgentTask | Run): BoardItem {
  return {
    kind,
    column: STATUS_TO_COLUMN[data.status] ?? 'pending',
    data,
  } as BoardItem
}

export function statusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  const map: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> = {
    pending: 'warn',
    running: 'info',
    succeeded: 'success',
    failed: 'danger',
    canceled: 'secondary',
    merged: 'success',
    archived: 'secondary',
  }
  return map[status] ?? 'secondary'
}
