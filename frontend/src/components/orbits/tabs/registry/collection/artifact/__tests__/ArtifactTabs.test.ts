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

function mountTabs(showModelAttachments: boolean, modelAttachmentsDisabled = false) {
  return mount(ArtifactTabs, {
    props: {
      showDataTab: false,
      showCard: true,
      showExperimentSnapshot: true,
      showModelAttachments,
      cardDisabled: false,
      experimentSnapshotDisabled: false,
      modelAttachmentsDisabled,
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

function attachmentsTab(wrapper: ReturnType<typeof mountTabs>) {
  return wrapper.findAllComponents(TabStub).find((tab) => tab.props('value') === 'attachments')
}

describe('ArtifactTabs', () => {
  it('hides the attachments tab for artifacts that cannot carry attachments', () => {
    expect(attachmentsTab(mountTabs(false))).toBeUndefined()
  })

  it('renders a disabled attachments tab while attachments are not confirmed', () => {
    expect(attachmentsTab(mountTabs(true, true))?.props('disabled')).toBe(true)
  })

  it('enables the attachments tab once attachments are confirmed', () => {
    expect(attachmentsTab(mountTabs(true, false))?.props('disabled')).toBe(false)
  })
})
