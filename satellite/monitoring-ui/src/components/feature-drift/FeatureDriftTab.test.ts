import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FeatureDriftTab from './FeatureDriftTab.vue'
import {
  ProfileStatus,
  SectionState,
  Severity,
  type FeatureDriftResponse,
  type ReferenceProfileResponse,
} from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeFeatureDrift, makeFeatureDriftDetail, makeReferenceProfile } from '@/test/fixtures'

function mountTab(props: {
  featureDrift: FeatureDriftResponse | null
  status: LoadStatus
  selectedFeature?: string | null
  referenceProfile?: ReferenceProfileResponse | null
  referenceProfileStatus?: LoadStatus
}) {
  return mount(FeatureDriftTab, {
    props: {
      selectedFeature: null,
      referenceProfile: makeReferenceProfile(),
      referenceProfileStatus: 'ready',
      ...props,
    },
    global: { stubs: { apexchart: true } },
  })
}

describe('FeatureDriftTab', () => {
  it('renders the ranked PSI list with per-feature status from the contract', () => {
    const wrapper = mountTab({ featureDrift: makeFeatureDrift(), status: 'ready' })

    const rows = wrapper.findAll('[data-testid="ranked-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('income')
    expect(rows[0].text()).toContain('0.31')
    expect(rows[0].find('[data-testid="severity-tag"]').text()).toBe('Critical')
    expect(rows[1].find('[data-testid="severity-tag"]').text()).toBe('Ok')
  })

  it('emits select-feature when a ranked row is clicked', async () => {
    const wrapper = mountTab({ featureDrift: makeFeatureDrift(), status: 'ready' })

    await wrapper.findAll('[data-testid="ranked-row"]')[0].trigger('click')

    expect(wrapper.emitted('select-feature')?.[0]).toEqual(['income'])
  })

  it('renders the selected feature detail with distribution and PSI-over-time', () => {
    const featureDrift = makeFeatureDrift({ selected: makeFeatureDriftDetail() })
    const wrapper = mountTab({ featureDrift, status: 'ready', selectedFeature: 'income' })

    const detail = wrapper.find('[data-testid="feature-detail"]')
    expect(detail.text()).toContain('income')
    expect(detail.text()).toContain('PSI 0.31')
    expect(detail.text()).toContain('Reference vs current distribution')
    expect(detail.text()).toContain('PSI over time')
    expect(wrapper.find('[data-testid="feature-detail-prompt"]').exists()).toBe(false)
  })

  it('prompts to select a feature when none is selected', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: null }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="feature-detail-prompt"]').exists()).toBe(true)
  })

  it('renders the multivariate PCA panel with shift, variance, and projection', () => {
    const wrapper = mountTab({ featureDrift: makeFeatureDrift(), status: 'ready' })

    const panel = wrapper.find('[data-testid="multivariate-panel"]')
    expect(panel.exists()).toBe(true)
    expect(panel.find('[data-testid="pca-shift"]').text()).toContain('3.40 σ')
    expect(panel.find('[data-testid="pca-shift"]').text()).toContain('reconstruction error')
    expect(panel.find('[data-testid="pca-psi"]').text()).toContain('1 / 2') // income ≥ 0.2
    expect(panel.find('[data-testid="pca-variance"]').text()).toContain('100.0%')
  })

  it('shows the PCA empty state when only univariate drift was computed', () => {
    const featureDrift = makeFeatureDrift({
      multivariate: {
        state: SectionState.EMPTY,
        status: Severity.OK,
        shift_value: null,
        shift_metric: null,
        explained_variance: [],
        feature_psi: [],
        reference_projection: [],
        current_projection: [],
      },
    })
    const wrapper = mountTab({ featureDrift, status: 'ready' })

    expect(wrapper.find('[data-testid="pca-empty"]').exists()).toBe(true)
  })

  it('renders the reference profile panel for the selected numeric feature', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail() }),
      status: 'ready',
      selectedFeature: 'income',
    })

    const panel = wrapper.find('[data-testid="reference-profile-panel"]')
    expect(panel.text()).toContain('Summary statistics')
    expect(panel.find('[data-testid="reference-edges"]').exists()).toBe(true)
    expect(panel.text()).toContain('training set (2026-01-05)')
  })

  it('renders category probabilities for a categorical reference feature', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail({ feature: 'region' }) }),
      status: 'ready',
      selectedFeature: 'region',
      referenceProfile: makeReferenceProfile({
        feature: {
          feature: 'region',
          kind: 'categorical',
          summary: { distinct: 3 },
          categories: ['north', 'south', 'east'],
          category_probabilities: [0.5, 0.3, 0.2],
        },
      }),
    })

    const panel = wrapper.find('[data-testid="reference-profile-panel"]')
    expect(panel.find('[data-testid="reference-categories"]').exists()).toBe(true)
    expect(panel.text()).toContain('north')
    expect(panel.text()).toContain('50.0%')
  })

  it('shows the not-computed-yet empty state when the worker has no drift results', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({
        state: SectionState.EMPTY,
        features: [],
        selected: null,
      }),
      status: 'ready',
    })

    expect(wrapper.find('[data-testid="state-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ranked-drift"]').exists()).toBe(false)
  })

  it('degrades gracefully for a placeholder profile — still renders drift content', () => {
    const featureDrift = makeFeatureDrift({ profile_status: ProfileStatus.PLACEHOLDER })
    const wrapper = mountTab({
      featureDrift,
      status: 'ready',
      referenceProfile: makeReferenceProfile({ profile_status: ProfileStatus.PLACEHOLDER }),
    })

    // The tab renders normally; the placeholder banner is shown by the shell, not this tab.
    expect(wrapper.find('[data-testid="feature-drift-tab"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="ranked-row"]')).toHaveLength(2)
    expect(wrapper.find('[data-testid="multivariate-panel"]').exists()).toBe(true)
  })

  it('renders for any classical-ML task type without task-specific branching', () => {
    // A classification-style feature set flows through the same ranked-list contract.
    const classification = makeFeatureDrift({
      features: [
        { feature: 'token_len', psi: 0.4, severity: Severity.CRITICAL },
        { feature: 'lang_code', psi: 0.02, severity: Severity.OK },
      ],
    })
    const wrapper = mountTab({ featureDrift: classification, status: 'ready' })

    const rows = wrapper.findAll('[data-testid="ranked-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('token_len')
  })
})
