import type { ExperimentSnapshotStatus } from '@/metric-buckets/types'
import { SNAPSHOT_RANGE_UNSUPPORTED } from '@/providers/snapshot-source/errors'
import { readErrorText } from './readErrorText'

export interface ExperimentStatusNotice {
  severity: 'error' | 'warn' | 'info'
  /** The read error code, or the first condition named in the text. */
  code: string
  text: string
}

function skippedRowsText(count: number): string {
  const formatted = count.toLocaleString('en-US')
  return count === 1
    ? '1 metric point was skipped because its step is not an integer.'
    : `${formatted} metric points were skipped because their steps are not integers.`
}

/** One line for an experiment whose data is not shown in full; null when all is well. */
export function experimentStatusNotice(
  status: ExperimentSnapshotStatus,
): ExperimentStatusNotice | null {
  if (status.error) {
    const { code } = status.error
    // A storage that stops answering range requests mid-session leaves what was read on screen.
    const shown =
      code === SNAPSHOT_RANGE_UNSUPPORTED ? 'Some data is not shown.' : 'Its data is not shown.'
    return { severity: 'error', code, text: `${readErrorText(code)} ${shown}` }
  }
  const warnings: [string, string][] = []
  if (status.unknownNewerRevision) {
    warnings.push([
      'unknown-newer-revision',
      'This experiment was written by a newer version. Some data may not be shown.',
    ])
  }
  if (status.skippedMetricRows !== null && status.skippedMetricRows > 0) {
    warnings.push(['skipped-rows', skippedRowsText(status.skippedMetricRows)])
  }
  const infos: [string, string][] = []
  if (status.transportFallback === 'range-ignored') {
    infos.push([
      'range-ignored',
      'The storage does not support range requests, so the experiment was loaded in full.',
    ])
  }
  const conditions = [...warnings, ...infos]
  const [first] = conditions
  if (!first) return null
  return {
    severity: warnings.length ? 'warn' : 'info',
    code: first[0],
    text: conditions.map(([, text]) => text).join(' '),
  }
}
