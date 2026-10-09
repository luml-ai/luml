import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AlertsTab from './AlertsTab.vue'
import { SectionState, type AlertsResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeAlerts } from '@/test/fixtures'

function mountTab(alerts: AlertsResponse | null = makeAlerts(), status: LoadStatus = 'ready') {
  return mount(AlertsTab, {
    props: { alerts, status },
    // the drawer teleports to the body; keep it inline so assertions stay on the wrapper
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('AlertsTab', () => {
  it('lists what is firing, by group, with readable numbers', () => {
    const wrapper = mountTab()

    expect(wrapper.find('[data-testid="alerts-summary"]').text()).toContain('2 open')
    expect(wrapper.find('[data-testid="alerts-summary"]').text()).toContain('1 critical')

    const rows = wrapper.findAll('[data-testid="alert-row"]')
    expect(rows).toHaveLength(2)
    // the subject is the feature when there is one, and the metric otherwise
    expect(rows[0].text()).toContain('income')
    expect(rows[0].text()).toContain('0.42')
    expect(rows[1].text()).toContain('error rate')
    expect(rows[1].text()).toContain('5.7%')
    // how long it has been firing
    expect(rows[0].text()).toContain('1h')
  })

  it('opens an alert with its numbers, timing and metric history', async () => {
    const wrapper = mountTab()

    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')

    const drawer = wrapper.find('[data-testid="alert-drawer"]')
    expect(drawer.text()).toContain('income')
    expect(drawer.text()).toContain('PSI')
    expect(drawer.find('[data-testid="alert-timing"]').text()).toContain('1h')
    // the chart is fed by the alert's own history
    expect(drawer.find('[data-testid="alert-history"]').findAll('apexchart-stub')).toHaveLength(1)
    expect(drawer.text()).toContain('built-in default')
  })

  it('says when a metric has no trend yet instead of drawing an empty chart', async () => {
    const wrapper = mountTab()

    await wrapper.findAll('[data-testid="alert-row"]')[1].trigger('click')

    expect(wrapper.find('[data-testid="alert-history-empty"]').exists()).toBe(true)
  })

  it('offers to follow a feature alert to the tab that explains it', async () => {
    const wrapper = mountTab()
    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')

    await wrapper.find('[data-testid="alert-show-feature"]').trigger('click')

    expect(wrapper.emitted('show-feature')?.[0]).toEqual([
      expect.objectContaining({ feature: 'income', group: 'feature_drift' }),
    ])
    // following the alert closes the panel it came from
    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(false)
  })

  it('a runtime alert has no feature to jump to', async () => {
    const wrapper = mountTab()

    await wrapper.findAll('[data-testid="alert-row"]')[1].trigger('click')

    expect(wrapper.find('[data-testid="alert-show-feature"]').exists()).toBe(false)
  })

  it('offers to acknowledge an open alert and reports it upward', async () => {
    const wrapper = mountTab()
    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')

    await wrapper.find('[data-testid="alert-acknowledge"]').trigger('click')

    expect(wrapper.emitted('acknowledge')?.[0]).toEqual([
      expect.objectContaining({ metric: 'feature_drift:income' }),
    ])
  })

  it('marks an acknowledged alert in the list itself', async () => {
    const alerts = makeAlerts()
    alerts.groups[0].alerts[0].state = 'acknowledged'
    const wrapper = mountTab(alerts)

    const rows = wrapper.findAll('[data-testid="alert-row"]')
    expect(rows[0].find('[data-testid="alert-acknowledged-chip"]').text()).toContain('seen')
    // the other one is untouched
    expect(rows[1].find('[data-testid="alert-acknowledged-chip"]').exists()).toBe(false)
    await rows[0].trigger('click')
    expect(wrapper.find('[data-testid="alert-acknowledged"]').exists()).toBe(true)
  })

  it('an acknowledged alert says so instead of offering the button again', async () => {
    const alerts = makeAlerts()
    alerts.groups[0].alerts[0].state = 'acknowledged'
    const wrapper = mountTab(alerts)
    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')

    expect(wrapper.find('[data-testid="alert-acknowledge"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="alert-acknowledged"]').text()).toContain(
      'stays on the list',
    )
    // still firing, so it is still counted
    expect(wrapper.find('[data-testid="alerts-summary"]').text()).toContain('2 open')
  })

  it('shows the quiet state when nothing is firing', () => {
    const wrapper = mountTab(makeAlerts({ groups: [] }))

    expect(wrapper.find('[data-testid="state-empty"]').text()).toContain('Nothing is firing')
    expect(wrapper.findAll('[data-testid="alert-row"]')).toHaveLength(0)
  })

  it('reports an unavailable store rather than an empty list', () => {
    const wrapper = mountTab(makeAlerts({ state: SectionState.UNAVAILABLE, groups: [] }))

    expect(wrapper.find('[data-testid="state-error"]').exists()).toBe(true)
  })
})
