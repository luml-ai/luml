import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MultivariatePanel from './MultivariatePanel.vue'
import { SectionState, Severity, type MultivariatePanel as PanelData } from '@/api/types'

function panel(overrides: Partial<PanelData> = {}): PanelData {
  return {
    state: SectionState.OK,
    status: Severity.WARNING,
    shift_value: 1.84,
    shift_metric: 'centroid shift',
    shift_unit: 'σ',
    dispersion_ratio: 1.12,
    outlier_rate: 0.041,
    explained_variance: [0.7, 0.24],
    feature_psi: [
      { feature: 'age', psi: 0.31, severity: Severity.CRITICAL },
      { feature: 'bmi', psi: 0.05, severity: Severity.OK },
    ],
    reference_projection: [],
    current_projection: [],
    reference_ellipse: [],
    current_ellipse: [],
    ...overrides,
  } as PanelData
}

describe('MultivariatePanel — how drift is measured', () => {
  it('names every measure with its value and caption', () => {
    const wrapper = mount(MultivariatePanel, { props: { panel: panel() } })

    const measures = wrapper.get('[data-testid="pca-measures"]')
    expect(measures.text()).toContain('How drift is measured')

    expect(wrapper.get('[data-testid="pca-shift"]').text()).toContain('1.84 σ')
    expect(wrapper.get('[data-testid="pca-shift"]').text()).toContain(
      'distance between population centroids',
    )
    expect(wrapper.get('[data-testid="pca-spread"]').text()).toContain('1.12×')
    expect(wrapper.get('[data-testid="pca-outliers"]').text()).toContain('4.1%')
    expect(wrapper.get('[data-testid="pca-psi"]').text()).toContain('1 / 2')
    expect(wrapper.get('[data-testid="pca-variance"]').text()).toContain('94.0%')
    expect(wrapper.get('[data-testid="pca-variance"]').text()).toContain(
      '2 components retained at training',
    )
  })

  it('shows a dash for a measure the window could not produce', () => {
    const wrapper = mount(MultivariatePanel, {
      props: { panel: panel({ dispersion_ratio: null, shift_value: null }) },
    })

    expect(wrapper.get('[data-testid="pca-spread"]').text()).toContain('—')
    expect(wrapper.get('[data-testid="pca-shift"]').text()).toContain('—')
  })

  it('explains how the comparison is made under the chart', () => {
    const wrapper = mount(MultivariatePanel, { props: { panel: panel() } })

    const text = wrapper.text()
    expect(text).toContain('compared to the reference Gaussian')
    expect(text).toContain('histogram bins computed during training')
  })

  it('says nothing but the empty state before the worker has a window', () => {
    const wrapper = mount(MultivariatePanel, {
      props: { panel: panel({ state: SectionState.EMPTY }) },
    })

    expect(wrapper.find('[data-testid="pca-measures"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="pca-empty"]').text()).toContain('has not been computed')
  })
})
