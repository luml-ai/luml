import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ExperimentStatusNotices from '../ExperimentStatusNotices.vue'
import type { ExperimentSnapshotStatus } from '@/metric-buckets/types'

function status(modelId: string, overrides: Partial<ExperimentSnapshotStatus> = {}) {
  return {
    modelId,
    revision: 3,
    transport: 'raw-range',
    transportFallback: null,
    unknownNewerRevision: false,
    skippedMetricRows: 0,
    error: null,
    ...overrides,
  } satisfies ExperimentSnapshotStatus
}

function mountNotices(statuses: ExperimentSnapshotStatus[]) {
  return mount(ExperimentStatusNotices, {
    props: {
      statuses,
      modelsInfo: { a: { name: 'Run A', color: '#000' }, b: { name: 'Run B', color: '#111' } },
    },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
}

function noticesFor(statuses: ExperimentSnapshotStatus[]) {
  return mountNotices(statuses)
    .findAll('[data-testid="experiment-status-notice"]')
    .map((notice) => notice.text())
}

describe('ExperimentStatusNotices', () => {
  it('shows nothing when every experiment is fine', () => {
    expect(noticesFor([status('a'), status('b', { skippedMetricRows: null })])).toEqual([])
  })

  it('says an experiment needs a newer viewer and keeps the others quiet', () => {
    const notices = noticesFor([
      status('a', { error: { code: 'needs-newer-reader', message: 'revision 9' } }),
      status('b'),
    ])
    expect(notices).toEqual([
      'Run A: This experiment needs a newer version of the viewer. Its data is not shown.',
    ])
  })

  it('shows a short text for the error code, never the raw message, and names the code', () => {
    const raw = "no such table: dynamic_metrics in 'SELECT * FROM x' for model 'a'"
    const wrapper = mountNotices([
      status('a', { error: { code: 'read-failed', message: raw } }),
      status('b', { error: { code: 'timed-out', message: raw } }),
      status('c', { skippedMetricRows: 2 }),
    ])
    const notices = wrapper.findAll('[data-testid="experiment-status-notice"]')
    expect(notices.map((notice) => notice.text())).toEqual([
      'Run A: The experiment could not be read. Its data is not shown.',
      'Run B: The request timed out. Its data is not shown.',
      'An experiment: Some metric points are not shown because their steps are not integers.',
    ])
    expect(notices.map((notice) => notice.attributes('data-code'))).toEqual([
      'read-failed',
      'timed-out',
      'skipped-rows',
    ])
  })

  it('says a zipped experiment is too large to open in the browser', () => {
    const error = { code: 'snapshot-too-large-for-browser', message: 'unzips to 3811495936 bytes' }
    expect(noticesFor([status('a', { transport: 'zip-full', error } as const)])).toEqual([
      'Run A: This experiment is too large to open in the browser. Upload it again with luml-sdk 0.6.0 or newer. Its data is not shown.',
    ])
  })

  it('says a storage request failed, whatever the cause', () => {
    const error = { code: 'snapshot-source-expired', message: 'connection dropped' }
    expect(noticesFor([status('a', { error } as const)])).toEqual([
      'Run A: The storage request failed. Reload the page. Its data is not shown.',
    ])
  })

  it('says metric steps above 2^53 are not shown', () => {
    const wrapper = mountNotices([status('a', { unsafeMetricSteps: true }), status('b')])
    const notices = wrapper.findAll('[data-testid="experiment-status-notice"]')
    expect(notices.map((notice) => notice.text())).toEqual([
      'Run A: Metric steps above 2^53 are not shown.',
    ])
    expect(notices[0]?.attributes('data-code')).toBe('unsafe-steps')
  })

  it('says an experiment written by a newer version may not be shown in full', () => {
    expect(noticesFor([status('b', { unknownNewerRevision: true })])).toEqual([
      'Run B: This experiment was written by a newer version. Some data may not be shown.',
    ])
  })

  it('says the storage ignored range requests', () => {
    expect(noticesFor([status('a', { transportFallback: 'range-ignored' })])).toEqual([
      'Run A: The storage does not support range requests, so the experiment was loaded in full.',
    ])
  })

  it('says skipped metric points are not shown, without a count', () => {
    const expected = [
      'Run A: Some metric points are not shown because their steps are not integers.',
    ]
    expect(noticesFor([status('a', { skippedMetricRows: 1200 })])).toEqual(expected)
    expect(noticesFor([status('a', { skippedMetricRows: 1 })])).toEqual(expected)
  })

  it('says so too when only a bucket answer left out fractional steps', () => {
    const wrapper = mountNotices([status('a', { fractionalMetricSteps: true }), status('b')])
    const notices = wrapper.findAll('[data-testid="experiment-status-notice"]')
    expect(notices.map((notice) => notice.text())).toEqual([
      'Run A: Some metric points are not shown because their steps are not integers.',
    ])
    expect(notices[0]?.attributes('data-code')).toBe('skipped-rows')
  })

  it('joins several conditions of one experiment into one line', () => {
    const notices = noticesFor([status('a', { unknownNewerRevision: true, skippedMetricRows: 3 })])
    expect(notices).toHaveLength(1)
    expect(notices[0]).toContain('newer version')
    expect(notices[0]).toContain('not integers')
  })
})
