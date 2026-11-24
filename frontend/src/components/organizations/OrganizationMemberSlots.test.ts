import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { Form } from '@primevue/forms'
import { Dialog } from 'primevue'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OrganizationCreateInvite from './OrganizationCreateInvite.vue'
import OrganizationLimits from './OrganizationLimits.vue'
import UiCircleProgress from '../ui/UiCircleProgress.vue'

const mocks = vi.hoisted(() => ({ createInvite: vi.fn(), toast: vi.fn() }))
const organizationStore = reactive({
  currentOrganization: { id: 'org' },
  organizationDetails: {
    members_limit: 3,
    total_members: 2,
    members: [{ id: 'owner' }, { id: 'member' }],
    invites: [] as { id: string }[],
    orbits_limit: 1,
    total_orbits: 0,
    satellites_limit: 2,
    total_satellites: 0,
    artifacts_limit: 50,
    total_artifacts: 0,
  },
  addInviteToCurrentOrganization: vi.fn(),
})
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('@/stores/invitations', () => ({
  useInvitationsStore: () => ({ createInvite: mocks.createInvite }),
}))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))

enableAutoUnmount(afterEach)
beforeEach(() => {
  vi.clearAllMocks()
  organizationStore.organizationDetails.members = [{ id: 'owner' }, { id: 'member' }]
  organizationStore.organizationDetails.members_limit = 3
  organizationStore.organizationDetails.invites = []
})

function mountInvite() {
  return shallowMount(OrganizationCreateInvite, {
    props: { isOwner: true },
    global: {
      stubs: {
        Button: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
      },
      directives: { tooltip: {} },
    },
  })
}

const limitMessage =
  'The organization has no free member slots. Cancel pending invites or upgrade to invite more people.'

describe('organization member slots', () => {
  it.each([1, 3])(
    'explains the limit with %i pending invites and frees a canceled slot',
    async (pending) => {
      organizationStore.organizationDetails.invites = Array.from({ length: pending }, (_, id) => ({
        id: String(id),
      }))
      const wrapper = mountInvite()
      await wrapper.findAll('button')[0].trigger('click')
      expect(wrapper.getComponent(Dialog).attributes('visible')).toBe('true')
      expect(wrapper.text()).toContain(limitMessage)
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

      wrapper.getComponent(Form).vm.$emit('submit', {
        valid: true,
        values: { email: 'invitee@example.com', role: 'member' },
      })
      await flushPromises()
      expect(mocks.createInvite).not.toHaveBeenCalled()

      organizationStore.organizationDetails.invites = []
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).not.toContain(limitMessage)
      expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    },
  )

  it('frees a slot after a member is removed', async () => {
    organizationStore.organizationDetails.invites = [{ id: 'pending' }]
    const wrapper = mountInvite()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    organizationStore.organizationDetails.members.pop()
    await wrapper.vm.$nextTick()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toContain(limitMessage)
  })

  it('sends an invite when a member slot is free', async () => {
    const wrapper = mountInvite()
    wrapper.getComponent(Form).vm.$emit('submit', {
      valid: true,
      values: { email: 'invitee@example.com', role: 'member' },
    })
    await flushPromises()
    expect(mocks.createInvite).toHaveBeenCalledExactlyOnceWith('org', {
      email: 'invitee@example.com',
      role: 'member',
    })
  })

  it('counts pending invites in the usage ring and explains the count', async () => {
    organizationStore.organizationDetails.invites = [{ id: 'pending' }]
    const wrapper = shallowMount(OrganizationLimits)
    expect(wrapper.findAllComponents(UiCircleProgress)[0].props('progress')).toBe(100)
    expect(wrapper.text()).toContain('3/3')
    expect(wrapper.text()).toContain('1 pending invite')

    organizationStore.organizationDetails.invites = []
    await wrapper.vm.$nextTick()
    expect(wrapper.findAllComponents(UiCircleProgress)[0].props('progress')).toBeCloseTo(200 / 3)
    expect(wrapper.text()).toContain('2/3')
  })
})
