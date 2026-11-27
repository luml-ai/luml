import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import UserInvitations from '../UserInvitations.vue'
import { useInvitationsStore } from '@/stores/invitations'
import type { Invitation, OwnershipTransfer } from '@/lib/api/api.interfaces'

const route = reactive({ name: 'home' as string })

vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('@/lib/api', () => ({ api: {} }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => ({}) }))

function mountInvitations() {
  return mount(UserInvitations, {
    global: { stubs: { InvitationsList: true, Dialog: true, 'd-button': true } },
  })
}

describe('UserInvitations bell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('lights up for an ownership transfer without organization invitations', () => {
    useInvitationsStore().ownershipTransfers = [{ id: 'transfer-1' } as OwnershipTransfer]

    expect(mountInvitations().find('.user-notification__circle').exists()).toBe(true)
  })

  it('lights up for an organization invitation', () => {
    useInvitationsStore().invitations = [{ id: 'invitation-1' } as Invitation]

    expect(mountInvitations().find('.user-notification__circle').exists()).toBe(true)
  })

  it('stays dark when nothing awaits a response', () => {
    expect(mountInvitations().find('.user-notification__circle').exists()).toBe(false)
  })
})
