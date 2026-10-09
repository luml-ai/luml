import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ReferenceProfileTab from './ReferenceProfileTab.vue'
import { SectionState, type ReferenceProfileResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeReferenceProfile } from '@/test/fixtures'

function mountTab(profile: ReferenceProfileResponse | null, status: LoadStatus = 'ready') {
  return mount(ReferenceProfileTab, {
    props: { profile, status },
    // the full-screen viewer teleports to the body; keep it inline for the assertions
    global: { stubs: { teleport: true } },
  })
}

describe('ReferenceProfileTab', () => {
  it('summarizes the document before showing it', () => {
    const wrapper = mountTab(makeReferenceProfile())

    const facts = wrapper.find('[data-testid="profile-facts"]').text()
    expect(facts).toContain('regression')
    expect(facts).toContain('1 numerical · 1 categorical')
    expect(facts).toContain('1,070')
    expect(facts).toContain('y_pred')
  })

  it('opens on the structure view and can switch to the raw file', async () => {
    const wrapper = mountTab(makeReferenceProfile())

    // the tree starts expanded at the top level, so the sections are readable at a glance
    const tree = wrapper.find('[data-testid="profile-tree"]')
    expect(tree.text()).toContain('feature_summaries')
    expect(tree.text()).toContain('task_type')
    expect(wrapper.find('[data-testid="profile-raw"]').exists()).toBe(false)

    await wrapper.find('[data-testid="profile-view-raw"]').trigger('click')

    const raw = wrapper.find('[data-testid="profile-raw"]')
    expect(raw.text()).toContain('"n_reference_samples": 1070')
    expect(wrapper.find('[data-testid="profile-tree"]').exists()).toBe(false)
  })

  it('offers the whole file for copying and for full screen', async () => {
    const wrapper = mountTab(makeReferenceProfile())

    expect(wrapper.find('[data-testid="copy-button"]').attributes('aria-label')).toBe(
      'Copy reference profile',
    )

    await wrapper.find('[data-testid="profile-fullscreen-open"]').trigger('click')

    const viewer = wrapper.find('[data-testid="field-fullscreen"]')
    expect(viewer.text()).toContain('reference_profile.json')
    expect(viewer.text()).toContain('"task_type": "regression"')
  })

  it('explains an artifact that carries no baseline', () => {
    const wrapper = mountTab(makeReferenceProfile({ state: SectionState.EMPTY, document: null }))

    expect(wrapper.find('[data-testid="state-empty"]').text()).toContain(
      'No reference profile loaded',
    )
    expect(wrapper.find('[data-testid="profile-facts"]').exists()).toBe(false)
  })
})
