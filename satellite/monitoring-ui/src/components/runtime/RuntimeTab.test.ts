import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RuntimeTab from './RuntimeTab.vue'
import { Granularity, SectionState, type RuntimeResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeRuntime } from '@/test/fixtures'

function mountTab(props: { runtime: RuntimeResponse | null; status: LoadStatus }) {
  return mount(RuntimeTab, {
    props: { ...props, granularity: Granularity.AUTO },
    // the alert drawer teleports to the body; keep it inline for the assertions
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('RuntimeTab', () => {
  it('shows the rollup metrics Overview leaves out', () => {
    const wrapper = mountTab({ runtime: makeRuntime(), status: 'ready' })
    const text = wrapper.text()

    expect(wrapper.findAll('[data-testid="metric-card"]')).toHaveLength(8)
    expect(text).toContain('Success rate')
    expect(text).toContain('95.2%')
    expect(text).toContain('Latency p50')
    expect(text).toContain('42 ms')
    expect(text).toContain('Timeouts')
    expect(text).toContain('Failed inferences')
  })

  it('breaks the window down by outcome and code', () => {
    const wrapper = mountTab({ runtime: makeRuntime(), status: 'ready' })

    const rows = wrapper.findAll('[data-testid="status-row"]')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('Success')
    expect(rows[0].text()).toContain('200')
    expect(rows[0].text()).toContain('1,180')
    // the row that separates a saturated server from a bad payload
    const timeout = rows[3]
    expect(timeout.text()).toContain('Timeout')
    expect(timeout.text()).toContain('504')
    expect(timeout.text()).toContain('0.2%')
  })

  it('plots the same three runtime series Overview does', () => {
    const wrapper = mountTab({ runtime: makeRuntime(), status: 'ready' })

    expect(wrapper.findAll('.charts .card')).toHaveLength(3)
    expect(wrapper.text()).toContain('Requests over time')
    expect(wrapper.text()).toContain('Latency p95 over time')
    expect(wrapper.findAll('[data-testid="chart-expand"]')).toHaveLength(3)
  })

  it('opens a runtime alert in the same sidebar the Alerts tab uses', async () => {
    const wrapper = mountTab({ runtime: makeRuntime(), status: 'ready' })

    const banner = wrapper.findAll('[data-testid="alert-banner"]')[0]
    expect(banner.element.tagName).toBe('BUTTON')
    await banner.trigger('click')

    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(true)
  })

  it('reads a window nobody called as empty, not as a wall of zeros', () => {
    const wrapper = mountTab({
      runtime: makeRuntime({
        request_count: 0,
        success_count: 0,
        success_rate: 0,
        error_count: 0,
        error_rate: 0,
        timeout_count: 0,
        failed_inference_count: 0,
        status_breakdown: [],
        alerts: [],
      }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="metric-card"]').exists()).toBe(false)
  })

  it('shows a section error when the store is unavailable', () => {
    const wrapper = mountTab({
      runtime: makeRuntime({ state: SectionState.UNAVAILABLE }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-error"]').exists()).toBe(true)
  })

  it('shows loading skeletons while the section is loading', () => {
    const wrapper = mountTab({ runtime: null, status: 'loading' })

    expect(wrapper.find('[data-testid="state-loading"]').exists()).toBe(true)
  })
})
