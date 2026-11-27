import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { Member, Organization, OrganizationDetails } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useUserStore } from '@/stores/user'
import OrganizationTransferOwnership from './OrganizationTransferOwnership.vue'

const harness = vi.hoisted(() => ({
  toastAdd: vi.fn(),
  transfer: vi.fn(),
  pending: vi.fn(),
  cancel: vi.fn(),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: harness.toastAdd }),
}))
vi.mock('@/lib/api', () => ({
  api: {
    requestOrganizationOwnership: harness.transfer,
    getPendingOwnershipTransfer: harness.pending,
    cancelOwnershipTransfer: harness.cancel,
  },
}))

function member(id: string, userId: string, role: OrganizationRoleEnum): Member {
  return {
    id,
    role,
    user: { id: userId, email: `${userId}@example.com`, full_name: userId },
  } as Member
}

function setup(members: Member[]) {
  const store = useOrganizationStore()
  store.availableOrganizations = [
    { id: 'organization-a', name: 'A', role: OrganizationRoleEnum.owner } as Organization,
  ]
  store.setCurrentOrganizationId('organization-a')
  store.organizationDetails = { members } as OrganizationDetails
  vi.spyOn(useUserStore(), 'getUserId', 'get').mockReturnValue('me')
  vi.spyOn(store, 'getAvailableOrganizations').mockResolvedValue()
  vi.spyOn(store, 'getOrganizationDetails').mockResolvedValue()
  return store
}

function mountComponent() {
  return shallowMount(OrganizationTransferOwnership, {
    global: {
      stubs: {
        Button: { template: '<button><slot /></button>' },
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
      },
    },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.resetAllMocks()
  harness.pending.mockResolvedValue(null)
})

it('offers every member except the current owner', async () => {
  setup([
    member('m-me', 'me', OrganizationRoleEnum.owner),
    member('m-alice', 'alice', OrganizationRoleEnum.admin),
    member('m-bob', 'bob', OrganizationRoleEnum.member),
  ])
  const wrapper = mountComponent()

  const options = wrapper.findComponent({ name: 'Select' }).vm.$attrs.options as Member[]
  expect(options.map((option) => option.id)).toEqual(['m-alice', 'm-bob'])
  wrapper.unmount()
})

it('asks to invite a member when nobody can take over', async () => {
  setup([member('m-me', 'me', OrganizationRoleEnum.owner)])
  const wrapper = mountComponent()

  expect(wrapper.text()).toContain('Invite a member')
  expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(false)
  expect(wrapper.findAll('button')[2].attributes('disabled')).toBeDefined()
  wrapper.unmount()
})

it('requests acceptance while retaining the existing owner', async () => {
  const store = setup([
    member('m-me', 'me', OrganizationRoleEnum.owner),
    member('m-bob', 'bob', OrganizationRoleEnum.member),
  ])
  harness.transfer.mockResolvedValue({
    id: 'request',
    recipient_email: 'bob@example.com',
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 604800000).toISOString(),
  })
  const wrapper = mountComponent()

  await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'm-bob')
  await wrapper.findAll('button')[2].trigger('click')
  await flushPromises()

  expect(harness.transfer).toHaveBeenCalledWith('organization-a', 'm-bob')
  expect(store.getAvailableOrganizations).not.toHaveBeenCalled()
  expect(store.getOrganizationDetails).not.toHaveBeenCalled()
  expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
  wrapper.unmount()
})

it('keeps the organization unchanged when the transfer fails', async () => {
  const store = setup([
    member('m-me', 'me', OrganizationRoleEnum.owner),
    member('m-bob', 'bob', OrganizationRoleEnum.member),
  ])
  harness.transfer.mockRejectedValue(new Error('Forbidden'))
  const wrapper = mountComponent()

  await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'm-bob')
  await wrapper.findAll('button')[2].trigger('click')
  await flushPromises()

  expect(store.getAvailableOrganizations).not.toHaveBeenCalled()
  expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  wrapper.unmount()
})

it('shows pending recipient and dates and allows cancellation', async () => {
  setup([member('m-me', 'me', OrganizationRoleEnum.owner)])
  harness.pending.mockResolvedValue({
    id: 'request',
    recipient_email: 'bob@example.com',
    created_at: '2026-01-01T00:00:00Z',
    expires_at: '2099-01-08T00:00:00Z',
  })
  const wrapper = mountComponent()
  await flushPromises()
  expect(wrapper.text()).toContain('bob@example.com')
  expect(wrapper.text()).toContain('Expires')
  await wrapper.findAll('button')[0].trigger('click')
  await flushPromises()
  expect(harness.cancel).toHaveBeenCalledWith('organization-a', 'request')
  expect(wrapper.text()).not.toContain('Ownership transfer requested for')
  wrapper.unmount()
})
