const STATUS_SEVERITY: Record<string, string> = {
  active: 'success',
  running: 'success',
  pending: 'warn',
  deletion_pending: 'warn',
  failed: 'danger',
  error: 'danger',
  deletion_failed: 'danger',
  not_responding: 'danger',
}

export function getDeploymentStatusSeverity(status: string): string {
  return STATUS_SEVERITY[status.toLowerCase()] ?? 'secondary'
}

export function getDeploymentStatusLabel(status: string): string {
  return status.replace(/_/g, ' ')
}
