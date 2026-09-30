import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ArtifactTabs from '../ArtifactTabs.vue'

const SlotStub = defineComponent({ template: '<div><slot /></div>' })
const TabStub = defineComponent({
  props: ['disabled', 'value'],
  template: '<div class="tab-stub"><slot /></div>',
})
const RouterLinkStub = defineComponent({
  props: ['to'],
  template: '<a><slot /></a>',
})

function mountTabs(showModelAttachments: boolean) {
  return mount(ArtifactTabs, {
    props: {
      showDataTab: false,
      showCard: true,
      showExperimentSnapshot: true,
      showModelAttachments,
      cardDisabled: false,
      experimentSnapshotDisabled: false,
    },
    global: {
      mocks: {
        $route: { name: 'artifact' },
        $router: { push: vi.fn() },
      },
      stubs: {
        Tabs: SlotStub,
        TabList: SlotStub,
        Tab: TabStub,
        RouterLink: RouterLinkStub,
      },
    },
  })
}

describe('ArtifactTabs', () => {
  it('hides the attachments tab when the artifact has no attachments', () => {
    expect(mountTabs(false).text()).not.toContain('Attachments')
  })

  it('shows the attachments tab when the artifact has attachments', () => {
    expect(mountTabs(true).text()).toContain('Attachments')
  })
})
