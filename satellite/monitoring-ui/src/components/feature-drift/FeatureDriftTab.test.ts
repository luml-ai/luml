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
import {
  makeAlerts,
  makeFeatureDrift,
  makeFeatureDriftDetail,
  makeReferenceProfile,
} from '@/test/fixtures'

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
    // the drawer teleports to the body; keep it inline so assertions stay on the wrapper
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('FeatureDriftTab', () => {
  it('opens an alert from its own section in the shared sidebar', async () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ alerts: makeAlerts().groups[0].alerts }),
      status: 'ready',
    })

    await wrapper.findAll('[data-testid="alert-banner"]')[0].trigger('click')

    expect(wrapper.find('[data-testid="alert-drawer"]').text()).toContain('income')

    await wrapper.find('[data-testid="alert-show-feature"]').trigger('click')
    expect(wrapper.emitted('show-feature')?.[0]).toEqual([
      expect.objectContaining({ feature: 'income' }),
    ])
  })

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

  it('names the kind of the selected feature next to its status', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail() }),
      status: 'ready',
      selectedFeature: 'income',
    })

    expect(wrapper.get('[data-testid="feature-kind"]').text()).toBe('Numerical')
  })

  it('keeps the reference profile behind a button until it is asked for', async () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail() }),
      status: 'ready',
      selectedFeature: 'income',
    })

    expect(wrapper.find('[data-testid="reference-profile-panel"]').exists()).toBe(false)

    await wrapper.get('[data-testid="open-reference-profile"]').trigger('click')

    const panel = wrapper.get('[data-testid="reference-profile-panel"]')
    expect(panel.text()).toContain('Summary statistics')
    expect(panel.find('[data-testid="reference-edges"]').exists()).toBe(true)

    // identity and provenance live in the drawer header, above the sections
    const drawer = wrapper.get('[data-testid="reference-drawer"]')
    expect(drawer.text()).toContain('income')
    expect(drawer.text()).toContain('numeric')
    expect(drawer.text()).toContain('training set (2026-01-05)')

    await wrapper.get('[data-testid="reference-drawer-close"]').trigger('click')
    expect(wrapper.find('[data-testid="reference-profile-panel"]').exists()).toBe(false)
  })

  it('shows category probabilities of a categorical feature in the drawer', async () => {
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

    expect(wrapper.get('[data-testid="feature-kind"]').text()).toBe('Categorical')

    await wrapper.get('[data-testid="open-reference-profile"]').trigger('click')

    const panel = wrapper.get('[data-testid="reference-profile-panel"]')
    expect(panel.find('[data-testid="reference-categories"]').exists()).toBe(true)
    expect(panel.text()).toContain('north')
    expect(panel.text()).toContain('50.0%')
  })

  it('keeps a long category label on one line and exposes it in full on hover', async () => {
    const longName = 'enterprise_customer_success_escalation_tier_three'
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail({ feature: 'segment' }) }),
      status: 'ready',
      selectedFeature: 'segment',
      referenceProfile: makeReferenceProfile({
        feature: {
          feature: 'segment',
          kind: 'categorical',
          summary: { distinct: 2 },
          categories: [longName, 'smb'],
          category_probabilities: [0.8, 0.2],
        },
      }),
    })

    await wrapper.get('[data-testid="open-reference-profile"]').trigger('click')

    const label = wrapper.findAll('.cat-name')[0]
    expect(label.text()).toBe(longName)
    expect(label.attributes('title')).toBe(longName)
  })

  it('closes the drawer when another feature is selected', async () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: makeFeatureDriftDetail() }),
      status: 'ready',
      selectedFeature: 'income',
    })

    await wrapper.get('[data-testid="open-reference-profile"]').trigger('click')
    expect(wrapper.find('[data-testid="reference-drawer"]').exists()).toBe(true)

    await wrapper.setProps({ selectedFeature: 'age' })

    expect(wrapper.find('[data-testid="reference-drawer"]').exists()).toBe(false)
  })

  it('explains both halves of the tab when there is nothing to rank', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ features: [], selected: null }),
      status: 'ready',
      selectedFeature: null,
    })

    const list = wrapper.get('[data-testid="ranked-empty"]')
    expect(list.text()).toContain('No features to rank')

    // with an empty ranking the detail panel must not send the reader back to the list
    const detail = wrapper.get('[data-testid="feature-detail-prompt"]')
    expect(detail.text()).toContain('Nothing to inspect yet')
    expect(detail.text()).not.toContain('Pick a feature')
  })

  it('asks for a selection while the ranking has features', () => {
    const wrapper = mountTab({
      featureDrift: makeFeatureDrift({ selected: null }),
      status: 'ready',
      selectedFeature: null,
    })

    expect(wrapper.get('[data-testid="feature-detail-prompt"]').text()).toContain('Pick a feature')
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
