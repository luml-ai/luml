export const COLUMN_DEFS = [
    { key: 'pending', label: 'Pending', severity: 'warn', icon: 'clock' },
    { key: 'running', label: 'Running', severity: 'info', icon: 'loader' },
    { key: 'completed', label: 'Completed', severity: 'success', icon: 'check-circle' },
    { key: 'merged', label: 'Merged', severity: 'info', icon: 'git-merge' },
];
export const STATUS_TO_COLUMN = {
    pending: 'pending',
    running: 'running',
    waiting_input: 'running',
    succeeded: 'completed',
    failed: 'completed',
    canceled: 'completed',
    merged: 'merged',
    archived: 'completed',
};
export const FAIL_STATUSES = new Set(['failed', 'canceled']);
export function toBoardItem(kind, data) {
    return {
        kind,
        column: STATUS_TO_COLUMN[data.status] ?? 'pending',
        data,
    };
}
export function displayStatus(status) {
    const map = {
        waiting_input: 'waiting for input',
    };
    return map[status] ?? status;
}
export function statusSeverity(status) {
    const map = {
        pending: 'warn',
        running: 'info',
        waiting_input: 'warn',
        succeeded: 'success',
        failed: 'danger',
        canceled: 'secondary',
        merged: 'info',
        archived: 'secondary',
    };
    return map[status] ?? 'secondary';
}
