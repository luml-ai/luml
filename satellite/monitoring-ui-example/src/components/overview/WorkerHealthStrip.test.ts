import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkerHealthStrip from './WorkerHealthStrip.vue'
import { SectionState } from '@/api/types'
import { makeWorkerHealth } from '@/test/fixtures'

function mountStrip(overrides = {}) {
  return mount(WorkerHealthStrip, { props: { health: makeWorkerHealth(overrides) } })
}

describe('WorkerHealthStrip', () => {
  it('says when the worker last ran and how far behind it was', () => {
    // a tick from a moment ago: the worker is keeping up
    const wrapper = mountStrip({ last_tick_at: new Date().toISOString() })

    const text = wrapper.find('[data-testid="worker-health"]').text()
    expect(text).toContain('42 windows')
    expect(text).toContain('18s behind')
    expect(wrapper.find('.dot').classes()).toContain('ok')
  })

  it('names the metrics that are failing instead of leaving an empty tab unexplained', () => {
    const wrapper = mountStrip({
      failures: [
        { metric: 'multivariate', error: 'singular covariance', at: '2026-07-07T12:00:00Z' },
      ],
    })

    expect(wrapper.find('[data-testid="worker-failures"]').text()).toContain('multivariate')
    expect(wrapper.find('.dot').classes()).toContain('failing')
  })

  it('says since when a metric has been failing', () => {
    const wrapper = mountStrip({
      failures: [{ metric: 'multivariate', error: 'singular', at: '2026-07-07T12:00:00Z' }],
      incidents: [
        {
          metric: 'multivariate',
          error: 'singular',
          started_at: '2026-07-07T11:00:00Z',
          ended_at: null,
          ongoing: true,
        },
      ],
    })

    expect(wrapper.find('[data-testid="worker-failures"]').text()).toContain('since')
  })

  it('remembers failures that already recovered — the counters would not', () => {
    const wrapper = mountStrip({
      failures: [],
      incidents: [
        {
          metric: 'output_drift',
          error: 'no output summary',
          started_at: '2026-07-07T10:00:00Z',
          ended_at: '2026-07-07T10:30:00Z',
          ongoing: false,
        },
      ],
    })

    const text = wrapper.find('[data-testid="worker-incidents"]').text()
    expect(text).toContain('1 recovered failure')
    expect(text).toContain('output_drift')
  })

  it('flags a worker that has gone quiet for several intervals', () => {
    const wrapper = mountStrip({ last_tick_at: new Date(Date.now() - 600_000).toISOString() })

    expect(wrapper.find('.dot').classes()).toContain('late')
  })

  it('says plainly when the worker has not run yet', () => {
    const wrapper = mountStrip({ running: false, last_tick_at: null, windows_processed: 0 })

    expect(wrapper.text()).toContain('has not run yet')
    expect(wrapper.find('.dot').classes()).toContain('idle')
  })

  it('stays out of the way when monitoring runs without a worker', () => {
    const wrapper = mount(WorkerHealthStrip, {
      props: { health: makeWorkerHealth({ state: SectionState.UNAVAILABLE }) },
    })

    expect(wrapper.find('[data-testid="worker-health"]').exists()).toBe(false)
  })
})
