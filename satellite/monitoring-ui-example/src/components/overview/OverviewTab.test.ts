import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import OverviewTab from './OverviewTab.vue'
import { Granularity, SectionState, type ModelKind, type OverviewResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeOverview } from '@/test/fixtures'

function mountTab(props: {
  overview: OverviewResponse | null
  status: LoadStatus
  modelKind?: ModelKind
}) {
  return mount(OverviewTab, {
    props: { modelKind: 'tabular', ...props, granularity: Granularity.AUTO },
    // the alert drawer teleports to the body; keep it inline for the assertions
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('OverviewTab', () => {
  it('opens an alert banner in the same sidebar the Alerts tab uses', async () => {
    const wrapper = mountTab({ overview: makeOverview(), status: 'ready' })

    const banner = wrapper.findAll('[data-testid="alert-banner"]')[0]
    expect(banner.element.tagName).toBe('BUTTON')
    await banner.trigger('click')

    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(true)
  })

  it('renders cards, alert banners, runtime charts, and top drifted features from the contract', () => {
    const overview = makeOverview()
    const wrapper = mountTab({ overview, status: 'ready' })

    expect(wrapper.findAll('[data-testid="metric-card"]')).toHaveLength(5)
    expect(wrapper.text()).toContain('Requests')
    expect(wrapper.text()).toContain('12,430')

    expect(wrapper.findAll('[data-testid="alert-banner"]')).toHaveLength(1)
    // the title is prose, the feature name stays verbatim next to it
    expect(wrapper.text()).toContain('Feature drift critical')
    expect(wrapper.text()).toContain('smoker')

    // one card per runtime series (requests / error rate / latency p95)
    expect(wrapper.findAll('.charts .card')).toHaveLength(3)
    expect(wrapper.text()).toContain('Requests over time')
    // each one opens full screen for a closer look
    expect(wrapper.findAll('[data-testid="chart-expand"]')).toHaveLength(3)

    const driftRows = wrapper.findAll('[data-testid="drifted-row"]')
    expect(driftRows).toHaveLength(2)
    expect(driftRows[0].text()).toContain('smoker')
    expect(driftRows[0].text()).toContain('0.31')
  })

  it('shows the not-computed-yet empty state when the worker has no results', () => {
    const wrapper = mountTab({
      overview: makeOverview({
        state: SectionState.EMPTY,
        cards: [],
        series: [],
        alert_banners: [],
        top_drifted_features: [],
      }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="metric-card"]').exists()).toBe(false)
  })

  it('shows a section error when the store is unavailable', () => {
    const wrapper = mountTab({
      overview: makeOverview({ state: SectionState.UNAVAILABLE }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-error"]').exists()).toBe(true)
  })

  it('shows loading skeletons while the section is loading', () => {
    const wrapper = mountTab({ overview: null, status: 'loading' })

    expect(wrapper.find('[data-testid="state-loading"]').exists()).toBe(true)
  })
})
