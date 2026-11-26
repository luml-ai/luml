import { SectionState, type WorkerHealthResponse } from '@/api/monitoring/interfaces'
import { formatTimestamp } from '@/utils/format'

const STALE_AFTER_MISSED_TICKS = 3

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

export function isWorkerHealthKnown(
  health: WorkerHealthResponse | null,
): health is WorkerHealthResponse {
  return !!health && health.state !== SectionState.UNAVAILABLE
}

export function getMissedTicks(health: WorkerHealthResponse | null, now = Date.now()): number {
  if (!health?.last_tick_at || !health.interval_seconds) return 0
  const since = (now - new Date(health.last_tick_at).getTime()) / 1000
  return since / health.interval_seconds
}

export function getWorkerStallSummary(
  health: WorkerHealthResponse | null,
  now = Date.now(),
): string | null {
  if (!isWorkerHealthKnown(health)) return null
  if (!health.running) {
    return 'The monitoring worker is not running, so no new windows are being computed.'
  }
  if (getMissedTicks(health, now) <= STALE_AFTER_MISSED_TICKS) return null
  const lastTick = formatTimestamp(health.last_tick_at)
  return `The monitoring worker has missed several runs (last run ${lastTick}). Sections may show older readings.`
}

export function getWorkerFacts(health: WorkerHealthResponse | null): string | null {
  if (!isWorkerHealthKnown(health) || !health.running) return null
  const parts: string[] = []
  if (health.last_tick_at) parts.push(`last run ${formatTimestamp(health.last_tick_at)}`)
  parts.push(`${health.windows_processed} window${health.windows_processed === 1 ? '' : 's'}`)
  if (health.last_lag_seconds != null) {
    parts.push(`${Math.round(health.last_lag_seconds)}s behind the window it closed`)
  }
  return parts.join(' · ')
}

export function getRecoveredIncidentsSummary(health: WorkerHealthResponse | null): string | null {
  if (!isWorkerHealthKnown(health) || health.failures.length) return null
  const recovered = health.incidents.filter((incident) => !incident.ongoing)
  if (!recovered.length) return null
  const metrics = [...new Set(recovered.map((incident) => incident.metric))].join(', ')
  const count = recovered.length
  return `${count} recovered failure${count === 1 ? '' : 's'} recently: ${metrics}`
}
