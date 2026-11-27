import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InvitationsList from '../InvitationsList.vue'
import { useInvitationsStore } from '@/stores/invitations'
import type { OwnershipTransfer } from '@/lib/api/api.interfaces'

vi.mock('@/lib/api', () => ({ api: {} }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => ({}) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

const placeholder = 'There are currently no invitations awaiting response.'

function mountList() {
  return mount(InvitationsList, {
    global: {
      stubs: { OwnershipTransferInvitations: true, ProgressSpinner: true, 'd-button': true },
    },
  })
}

describe('InvitationsList placeholder', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useInvitationsStore().isLoaded = true
  })

  it('is hidden while an ownership transfer awaits a response', () => {
    useInvitationsStore().ownershipTransfers = [{ id: 'transfer-1' } as OwnershipTransfer]

    expect(mountList().text()).not.toContain(placeholder)
  })

  it('is shown when there are neither invitations nor ownership transfers', () => {
    expect(mountList().find('.placeholder').text()).toBe(placeholder)
  })
})
