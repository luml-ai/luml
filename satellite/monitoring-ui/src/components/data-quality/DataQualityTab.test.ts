import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DataQualityTab from './DataQualityTab.vue'
import { SectionState, Severity, Window, type DataQualityResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeDataQuality } from '@/test/fixtures'

function mountTab(props: {
  dataQuality: DataQualityResponse | null
  status: LoadStatus
  window?: Window
}) {
  return mount(DataQualityTab, {
    props,
    // the drawer teleports to the body; keep it inline so assertions stay on the wrapper
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('DataQualityTab', () => {
  it('says so when the table describes a window from outside the selected range', () => {
    // The snapshot is read with no time bound, so a stale reading otherwise looks current.
    const wrapper = mountTab({
      dataQuality: makeDataQuality({ stale: true, computed_at: '2026-06-05T09:00:00Z' }),
      status: 'ready',
      window: Window.H24,
    })

    const notice = wrapper.find('[data-testid="stale-window-notice"]')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('24h')
    // the reading itself is still served rather than hidden behind the notice
    expect(wrapper.findAll('[data-testid="dq-row"]').length).toBeGreaterThan(0)
  })

  it('stays quiet when the window is inside the range', () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    expect(wrapper.find('[data-testid="stale-window-notice"]').exists()).toBe(false)
  })

  it('renders the per-feature table from the contract, including rates and status', () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    const rows = wrapper.findAll('[data-testid="dq-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[1].text()).toContain('region')
    expect(rows[1].text()).toContain('20.0%') // missing_rate 0.2
    expect(rows[1].text()).toContain('5.0%') // type_error_rate 0.05
    expect(rows[1].find('[data-testid="severity-tag"]').text()).toBe('Critical')
    expect(rows[0].find('[data-testid="severity-tag"]').text()).toBe('Ok')
  })

  it('names the check behind the range / unseen column and flags rates past the thresholds', () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    const rows = wrapper.findAll('[data-testid="dq-row"]')
    // a numerical feature reports range violations, a categorical one unseen categories
    expect(rows[0].text()).toContain('2.0% out of range')
    expect(rows[1].text()).toContain('10.0% unseen')
    // 0.1% missing is under the 1% warning line, 20% is past the 5% critical one
    expect(rows[0].findAll('.warn, .critical')).toHaveLength(0)
    expect(rows[1].find('.critical').text()).toBe('20.0%')
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

  it('opens the invalid-values panel for the clicked feature and closes it again', async () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })

    expect(wrapper.find('[data-testid="invalid-values-drawer"]').exists()).toBe(false)

    await wrapper.findAll('[data-testid="dq-row"]')[1].trigger('click')

    const drawer = wrapper.find('[data-testid="invalid-values-drawer"]')
    expect(drawer.text()).toContain('region')
    expect(drawer.text()).toContain('Categorical')
    expect(drawer.text()).toContain('1,070 values checked')
    // the row's verdict travels with it into the panel header
    expect(drawer.find('[data-testid="severity-tag"]').text()).toBe('Critical')
    expect(drawer.find('[data-testid="dq-unseen-categories"]').text()).toContain('antarctica')

    // the page must not scroll away behind the panel while it is open
    expect(document.body.style.overflow).toBe('hidden')

    // opening a row asks for that feature's history; closing cancels the request
    expect(wrapper.emitted('inspect')?.at(-1)).toEqual(['region'])

    await drawer.find('[data-testid="invalid-values-drawer-close"]').trigger('click')
    expect(wrapper.find('[data-testid="invalid-values-drawer"]').exists()).toBe(false)
    expect(document.body.style.overflow).toBe('')
    expect(wrapper.emitted('inspect')?.at(-1)).toEqual([null])
  })

  it('follows the selected feature into the next window, and drops it when it is gone', async () => {
    const wrapper = mountTab({ dataQuality: makeDataQuality(), status: 'ready' })
    await wrapper.findAll('[data-testid="dq-row"]')[1].trigger('click')

    const next = makeDataQuality()
    next.features[1].invalid!.unseen_categories = [{ value: 'pluto', count: 4 }]
    await wrapper.setProps({ dataQuality: next })
    expect(wrapper.find('[data-testid="invalid-values-drawer"]').text()).toContain('pluto')

    await wrapper.setProps({
      dataQuality: makeDataQuality({ features: [makeDataQuality().features[0]] }),
    })
    expect(wrapper.find('[data-testid="invalid-values-drawer"]').exists()).toBe(false)
    expect(wrapper.emitted('inspect')?.at(-1)).toEqual([null])
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

})
