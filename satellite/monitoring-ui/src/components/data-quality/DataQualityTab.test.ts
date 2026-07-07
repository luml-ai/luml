import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DataQualityTab from './DataQualityTab.vue'
import { SectionState, Severity, type DataQualityResponse, type TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeDataQuality, makeTraces } from '@/test/fixtures'

function mountTab(props: {
  dataQuality: DataQualityResponse | null
  status: LoadStatus
  traces?: TracesResponse | null
  tracesStatus?: LoadStatus
}) {
  return mount(DataQualityTab, {
    props: {
      traces: makeTraces(),
      tracesStatus: 'ready',
      ...props,
    },
    global: { stubs: { apexchart: true } },
  })
}

describe('DataQualityTab', () => {
  it('renders the per-feature table from the contract, including rates and status', () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    const rows = wrapper.findAll('[data-testid="dq-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[1].text()).toContain('income')
    expect(rows[1].text()).toContain('20.0%') // missing_rate 0.2
    expect(rows[1].text()).toContain('10.0%') // range/unseen 0.1
    expect(rows[1].find('[data-testid="severity-tag"]').text()).toBe('Critical')
    expect(rows[0].find('[data-testid="severity-tag"]').text()).toBe('Ok')
  })

  it('renders from the contract for any classical-ML task without task-specific branching', () => {
    // Classification-style features — the component has no task_type input and cannot branch.
    const classification = makeDataQuality({
      features: [
        {
          feature: 'pixel_intensity',
          missing_rate: 0.0,
          type_error_rate: 0.0,
          range_unseen_rate: 0.0,
          status: Severity.OK,
        },
        {
          feature: 'category_code',
          missing_rate: 0.03,
          type_error_rate: 0.0,
          range_unseen_rate: 0.4,
          status: Severity.WARNING,
        },
      ],
    })
    const wrapper = mountTab({ dataQuality: classification, status: 'ready' })

    const rows = wrapper.findAll('[data-testid="dq-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('pixel_intensity')
    expect(rows[1].find('[data-testid="severity-tag"]').text()).toBe('Warning')
  })

  it('shows the not-computed-yet empty state and no table when the worker has no results', () => {
    const wrapper = mountTab({
      dataQuality: makeDataQuality({ state: SectionState.EMPTY, features: [] }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="data-quality-table"]').exists()).toBe(false)
  })

  it('shows a section error when the store is unavailable', () => {
    const wrapper = mountTab({
      dataQuality: makeDataQuality({ state: SectionState.UNAVAILABLE }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-error"]').exists()).toBe(true)
  })

  it('renders the local Traces panel with recent inference calls', () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    expect(wrapper.find('[data-testid="traces-panel"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="trace-row"]')).toHaveLength(2)
  })

  it('emits a traces-page request when paging', async () => {
    const wrapper = mountTab({
      dataQuality: makeDataQuality(),
      status: 'ready',
      traces: makeTraces({ total: 60, offset: 0, limit: 20 }),
      tracesStatus: 'ready',
    })

    await wrapper.find('[data-testid="traces-next"]').trigger('click')

    expect(wrapper.emitted('traces-page')?.[0]).toEqual([20])
  })

  it('shows the traces empty state when there are no inference calls', () => {
    const wrapper = mountTab({
      dataQuality: makeDataQuality(),
      status: 'ready',
      traces: makeTraces({ state: SectionState.EMPTY, rows: [], total: 0 }),
      tracesStatus: 'ready',
    })

    expect(wrapper.find('[data-testid="traces-panel"] [data-testid="state-empty"]').exists()).toBe(
      true,
    )
  })
})
