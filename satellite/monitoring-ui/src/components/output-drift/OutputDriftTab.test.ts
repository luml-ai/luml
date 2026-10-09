import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import OutputDriftTab from './OutputDriftTab.vue'
import { SectionState, type OutputDriftResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeOutputDrift } from '@/test/fixtures'

function mountTab(props: { outputDrift: OutputDriftResponse | null; status: LoadStatus }) {
  return mount(OutputDriftTab, {
    props,
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('OutputDriftTab', () => {
  it('shows the score, its severity, and what it was computed over', () => {
    const wrapper = mountTab({ outputDrift: makeOutputDrift(), status: 'ready' })
    const headline = wrapper.find('[data-testid="output-headline"]')

    expect(headline.text()).toContain('y_pred')
    expect(headline.text()).toContain('0.42')
    expect(headline.text()).toContain('Critical')
    expect(headline.text()).toContain('120 predictions')
  })

  it('draws the distribution, the PSI history, and the prediction band', () => {
    const wrapper = mountTab({ outputDrift: makeOutputDrift(), status: 'ready' })
    const text = wrapper.text()

    expect(text).toContain('Reference vs current distribution')
    expect(text).toContain('PSI over time')
    expect(text).toContain('Prediction trend')
    expect(text).toContain('p05–p95')
    // every chart opens full screen, like the rest of the dashboard
    expect(wrapper.findAll('[data-testid="chart-expand"]')).toHaveLength(3)
  })

  it('keeps the layout honest when a window has no distribution yet', () => {
    // windows materialized before this feature carry psi and trend but no distribution
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({ distribution: null }),
      status: 'ready',
    })

    expect(wrapper.text()).toContain('No distribution in this window yet')
    expect(wrapper.text()).toContain('PSI over time')
  })

  it('hides the band section for categorical outputs', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({ kind: 'categorical', trend: [] }),
      status: 'ready',
    })

    expect(wrapper.text()).not.toContain('Prediction trend')
  })

  it('shows which classes moved for a classification output', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({
        kind: 'categorical',
        trend: [],
        top_changed: [
          { label: 'virginica', reference: 0.33, current: 0.6, delta: 0.27 },
          { label: 'setosa', reference: 0.34, current: 0.2, delta: -0.14 },
        ],
        class_share_trend: [
          {
            key: 'class_virginica',
            label: 'virginica',
            unit: 'ratio',
            points: [
              { t: '2026-07-07T10:00:00Z', value: 0.33 },
              { t: '2026-07-07T11:00:00Z', value: 0.6 },
            ],
          },
        ],
      }),
      status: 'ready',
    })

    const shifts = wrapper.find('[data-testid="top-changed-classes"]')
    expect(shifts.text()).toContain('virginica')
    expect(shifts.text()).toContain('33.0% → 60.0%')
    expect(shifts.text()).toContain('+27.0pp')
    expect(wrapper.text()).toContain('Class share over time')
  })

  it('shows the confidence early warning when the artifact reports scores', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({
        kind: 'categorical',
        trend: [],
        confidence: {
          psi: 0.42,
          mean: 0.71,
          low_confidence_rate: 0.3,
          low_confidence_threshold: 0.88,
          distribution: {
            kind: 'numeric',
            bins: [{ label: '0.9–1', reference: 0.7, current: 0.2 }],
          },
          mean_over_time: {
            key: 'confidence_mean',
            label: 'Mean confidence',
            points: [
              { t: '2026-07-07T10:00:00Z', value: 0.93 },
              { t: '2026-07-07T11:00:00Z', value: 0.71 },
            ],
          },
        },
      }),
      status: 'ready',
    })

    const stats = wrapper.find('[data-testid="confidence-stats"]')
    expect(stats.text()).toContain('Confidence PSI')
    expect(stats.text()).toContain('0.42')
    expect(stats.text()).toContain('71.0%')
    expect(stats.text()).toContain('30.0% of predictions below the training q05 (88.0%)')
    expect(wrapper.text()).toContain('Confidence distribution')
    expect(wrapper.text()).toContain('Mean confidence over time')
  })

  it('shows no confidence block when the artifact reports only labels', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({ kind: 'categorical', trend: [] }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="confidence-stats"]').exists()).toBe(false)
  })

  it('ranks probability drift by class and shows the coin-flip zone', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({
        kind: 'categorical',
        trend: [],
        probabilities: {
          per_class: [
            { label: 'dog', psi: 0.42, mean: 0.61 },
            { label: 'cat', psi: 0.08, mean: 0.39 },
          ],
          near_threshold: {
            rate: 0.5,
            reference_rate: 0.02,
            threshold: 0.5,
            positive_class: 'dog',
          },
        },
      }),
      status: 'ready',
    })

    const block = wrapper.find('[data-testid="probability-drift"]')
    expect(block.text()).toContain('dog')
    expect(block.text()).toContain('PSI 0.42')
    expect(wrapper.find('[data-testid="near-threshold"]').text()).toContain(
      '50.0% of predictions within the coin-flip zone',
    )
  })

  it('lists every forecast horizon with the worst one leading the headline', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({
        kind: 'forecast',
        name: 'y[h7]',
        trend: [],
        horizons: [
          { label: 'h7', psi: 0.6, mean: 37, count: 20 },
          { label: 'h1', psi: 0.05, mean: 20, count: 20 },
        ],
      }),
      status: 'ready',
    })

    const block = wrapper.find('[data-testid="horizon-drift"]')
    expect(block.text()).toContain('h7')
    expect(block.text()).toContain('PSI 0.60')
    expect(block.text()).toContain('20 forecasts')
    // the headline names the horizon the charts describe
    expect(wrapper.find('[data-testid="output-headline"]').text()).toContain('y[h7]')
  })

  it('shows no class block for a regression output', () => {
    const wrapper = mountTab({ outputDrift: makeOutputDrift(), status: 'ready' })

    expect(wrapper.find('[data-testid="top-changed-classes"]').exists()).toBe(false)
  })

  it('opens an output alert in the same sidebar the Alerts tab uses', async () => {
    const wrapper = mountTab({ outputDrift: makeOutputDrift(), status: 'ready' })

    const banner = wrapper.findAll('[data-testid="alert-banner"]')[0]
    await banner.trigger('click')

    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(true)
  })

  it('shows the not-computed-yet empty state without output windows', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({ state: SectionState.EMPTY }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="output-headline"]').exists()).toBe(false)
  })

  it('marks a snapshot that fell out of the selected range as stale', () => {
    const wrapper = mountTab({
      outputDrift: makeOutputDrift({ stale: true, computed_at: '2026-07-05T10:00:00Z' }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="stale-window-notice"]').exists()).toBe(true)
  })
})
