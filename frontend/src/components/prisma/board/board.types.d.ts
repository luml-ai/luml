import type { AgentTask, Run } from '@/lib/api/prisma/prisma.interfaces';
export type BoardColumn = 'pending' | 'running' | 'completed' | 'merged';
export interface ColumnDef {
    key: BoardColumn;
    label: string;
    severity: 'warn' | 'info' | 'success' | 'danger';
    icon: string;
}
export declare const COLUMN_DEFS: ColumnDef[];
export declare const STATUS_TO_COLUMN: Record<string, BoardColumn>;
export declare const FAIL_STATUSES: Set<string>;
export type BoardItem = {
    kind: 'task';
    column: BoardColumn;
    data: AgentTask;
} | {
    kind: 'run';
    column: BoardColumn;
    data: Run;
};
export declare function toBoardItem(kind: 'task', data: AgentTask): BoardItem;
export declare function toBoardItem(kind: 'run', data: Run): BoardItem;
export declare function displayStatus(status: string): string;
export declare function statusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary';
