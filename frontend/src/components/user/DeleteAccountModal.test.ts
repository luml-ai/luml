import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Member, Organization } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import DeleteAccountModal from './DeleteAccountModal.vue'

const mocks = vi.hoisted(() => ({
  getOrganizations: vi.fn(),
  getOrganizationMembers: vi.fn(),
  transferOrganizationOwnership: vi.fn(),
  deleteAccount: vi.fn(),
  getAvailableOrganizations: vi.fn(),
  push: vi.fn(),
  toast: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    getOrganizations: mocks.getOrganizations,
    getOrganizationMembers: mocks.getOrganizationMembers,
    transferOrganizationOwnership: mocks.transferOrganizationOwnership,
  },
}))
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ getUserId: 'self', deleteAccount: mocks.deleteAccount }),
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ getAvailableOrganizations: mocks.getAvailableOrganizations }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))

const organization = (id: string, role: OrganizationRoleEnum) =>
  ({ id, name: `${id} org`, role }) as Organization

const member = (id: string, role: OrganizationRoleEnum): Member => ({
  id: `member-${id}`,
  organization_id: 'organization',
  role,
  user: {
    id,
    email: `${id}@example.com`,
    full_name: id,
    photo: '',
    disabled: false,
    has_api_key: false,
  },
  created_at: new Date('2025-01-01'),
  updated_at: null,
})

const membersByOrganization: Record<string, Member[]> = {
  personal: [member('self', OrganizationRoleEnum.owner)],
  shared: [
    member('self', OrganizationRoleEnum.owner),
    member('alice', OrganizationRoleEnum.member),
    member('bob', OrganizationRoleEnum.admin),
  ],
  'co-owned': [
    member('self', OrganizationRoleEnum.owner),
    member('carol', OrganizationRoleEnum.owner),
  ],
}

const mountModal = () =>
  mount(DeleteAccountModal, {
    props: { show: true },
    global: {
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
        Button: {
          props: ['label', 'disabled', 'loading'],
          emits: ['click'],
          template:
            '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
        },
        Select: {
          name: 'Select',
          props: ['modelValue', 'options'],
          emits: ['update:modelValue'],
          template: '<select />',
        },
        ProgressSpinner: true,
      },
    },
  })

const findButton = (wrapper: ReturnType<typeof mountModal>, label: string) => {
  const button = wrapper.findAll('button').find((item) => item.text() === label)
  if (!button) throw new Error(`Button "${label}" not found`)
  return button
}

describe('DeleteAccountModal', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getOrganizations.mockResolvedValue([
      organization('personal', OrganizationRoleEnum.owner),
      organization('shared', OrganizationRoleEnum.owner),
      organization('co-owned', OrganizationRoleEnum.owner),
      organization('joined', OrganizationRoleEnum.member),
    ])
    mocks.getOrganizationMembers.mockImplementation(
      async (organizationId: string) => membersByOrganization[organizationId],
    )
  })

  it('explains what happens to each organization', async () => {
    const wrapper = mountModal()
    await flushPromises()

    const items = wrapper.findAll('li').map((item) => item.text())
    expect(items[0]).toContain('will be deleted')
    expect(items[1]).toContain('Transfer ownership')
    expect(items[2]).toContain('You will be removed')
    expect(items[2]).not.toContain('Transfer ownership')
    expect(items[3]).toContain('You will be removed')
    expect(mocks.getOrganizationMembers).not.toHaveBeenCalledWith('joined')
  })

  it('transfers ownership to the selected member', async () => {
    mocks.transferOrganizationOwnership.mockResolvedValue(
      member('alice', OrganizationRoleEnum.owner),
    )
    const wrapper = mountModal()
    await flushPromises()

    await findButton(wrapper, 'Transfer ownership').trigger('click')
    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.props('options').map((option: Member) => option.user.id)).toEqual([
      'alice',
      'bob',
    ])
    select.vm.$emit('update:modelValue', 'member-alice')
    await flushPromises()
    await findButton(wrapper, 'Transfer').trigger('click')
    await flushPromises()

    expect(mocks.transferOrganizationOwnership).toHaveBeenCalledWith('shared', 'member-alice')
    expect(wrapper.findAll('li')[1].text()).toContain('Ownership transferred to alice')
    expect(mocks.getAvailableOrganizations).toHaveBeenCalled()
  })

  it('deletes the account after confirmation', async () => {
    const wrapper = mountModal()
    await flushPromises()

    await findButton(wrapper, 'Yes, delete my account').trigger('click')
    await flushPromises()

    expect(mocks.deleteAccount).toHaveBeenCalledOnce()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'sign-up' })
  })

  it('keeps the dialog open when deletion fails', async () => {
    mocks.deleteAccount.mockRejectedValue(new Error('Organization membership changed'))
    const wrapper = mountModal()
    await flushPromises()

    await findButton(wrapper, 'Yes, delete my account').trigger('click')
    await flushPromises()

    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Organization membership changed' }),
    )
  })
})
