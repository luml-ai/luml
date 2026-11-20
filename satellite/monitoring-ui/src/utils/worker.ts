import type { WorkerHealthResponse } from '@/api/monitoring/interfaces'
import { formatTimestamp } from '@/utils/format'

export function isRecordingOff(health: WorkerHealthResponse | null): boolean {
  const state = health?.recording?.state
  return state != null && state !== 'recording'
}

export function getRecordingDetail(health: WorkerHealthResponse | null): string {
  const reason = health?.recording?.reason
  const consequence =
    'New calls are not being recorded, so charts and tables stop at the last recorded call.'
  return reason ? `${reason} ${consequence}` : consequence
}

export function getWorkerFailureSummary(health: WorkerHealthResponse | null): string | null {
  const failures = health?.failures ?? []
  if (!failures.length) return null
  const metrics = [...new Set(failures.map((failure) => failure.metric))].join(', ')
  const ongoing = (health?.incidents ?? []).find((incident) => incident.ongoing)
  const since = ongoing ? ` since ${formatTimestamp(ongoing.started_at)}` : ''
  return `Failed to compute ${metrics}${since}. Their sections may show older readings.`
}
