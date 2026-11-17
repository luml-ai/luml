import {
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TIMED_OUT,
  TOO_MANY_BUCKETS,
  type ExperimentReadErrorCode,
} from '@/metric-buckets/types'
import {
  SNAPSHOT_FORMAT,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
} from '@/providers/snapshot-source/errors'

// Error messages hold ids, URLs or SQL, so the UI shows only these texts.
const READ_ERROR_TEXTS: Record<ExperimentReadErrorCode, string> = {
  [NEEDS_NEWER_READER]: 'This experiment needs a newer version of the viewer.',
  [TOO_MANY_BUCKETS]: 'The chart asked for too much data. Zoom in to see it.',
  [INVALID_LEVEL]: 'The chart asked for data that does not exist.',
  [READ_FAILED]: 'The experiment could not be read.',
  [TIMED_OUT]: 'The request timed out.',
  [SNAPSHOT_SOURCE_EXPIRED]: 'The storage refused the request. Reload the page.',
  [SNAPSHOT_RANGE_UNSUPPORTED]: 'The storage stopped answering range requests. Reload the page.',
  [SNAPSHOT_SOURCE_REDIRECT]: 'The storage sent the request to another address, which refused it.',
  [SNAPSHOT_SOURCE_TOO_LARGE]:
    'The storage does not support range requests, and this experiment is too large to load in full.',
  [SNAPSHOT_TOO_LARGE_FOR_BROWSER]:
    'This experiment is too large to open in the browser. Upload it again with luml-sdk 0.6.0 or newer.',
  [SNAPSHOT_SOURCE_PAGE]:
    'The storage sent a web page instead of the data. The sign-in may have expired. Reload the page.',
  [SNAPSHOT_FORMAT]: 'This experiment is not a valid snapshot.',
}

export function readErrorText(code: ExperimentReadErrorCode): string {
  return READ_ERROR_TEXTS[code] ?? READ_ERROR_TEXTS[READ_FAILED]
}
