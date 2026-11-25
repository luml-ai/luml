import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import OwnershipTransferInvitations from './OwnershipTransferInvitations.vue'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  respond: vi.fn(),
  refresh: vi.fn(),
  switch: vi.fn(),
  toast: vi.fn(),
}))
vi.mock('@/lib/api', () => ({
  api: { getOwnershipTransfers: mocks.get, respondToOwnershipTransfer: mocks.respond },
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({
    getAvailableOrganizations: mocks.refresh,
    switchOrganization: mocks.switch,
  }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))
const request = {
  id: 'request',
  organization_id: 'organization',
  organization_name: 'Example',
  sender_email: 'sender@example.com',
  expires_at: new Date(Date.now() + 604800000).toISOString(),
}
function setup() {
  return shallowMount(OwnershipTransferInvitations, {
    global: {
      stubs: {
        Button: {
          props: ['label', 'disabled'],
          template: '<button :disabled="disabled">{{ label }}</button>',
        },
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}
beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  mocks.get.mockResolvedValue([request])
  mocks.respond.mockResolvedValue({})
})
it('requires a responsibility confirmation before accepting', async () => {
  const wrapper = setup()
  await flushPromises()
  await wrapper.findAll('button')[1].trigger('click')
  expect(mocks.respond).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('full control and responsibility')
  await wrapper.findAll('button')[3].trigger('click')
  await flushPromises()
  expect(mocks.respond).toHaveBeenCalledWith(request, 'accept')
  expect(mocks.switch).toHaveBeenCalledWith('organization')
  wrapper.unmount()
})
it('declines from invitations without settings access', async () => {
  const wrapper = setup()
  await flushPromises()
  await wrapper.findAll('button')[0].trigger('click')
  await flushPromises()
  expect(mocks.respond).toHaveBeenCalledWith(request, 'decline')
  expect(mocks.switch).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('reports a closed request and refreshes the list', async () => {
  const wrapper = setup()
  await flushPromises()
  mocks.respond.mockRejectedValue(new Error('Ownership transfer request is no longer pending.'))
  mocks.get.mockResolvedValue([])
  await wrapper.findAll('button')[0].trigger('click')
  await flushPromises()
  expect(wrapper.find('article').exists()).toBe(false)
  expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  wrapper.unmount()
})
