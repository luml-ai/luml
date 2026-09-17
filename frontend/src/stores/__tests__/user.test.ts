import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getMe: vi.fn(),
}))
const invitationsStore = vi.hoisted(() => ({
  getInvitations: vi.fn(),
  reset: vi.fn(),
}))
const organizationStore = vi.hoisted(() => ({
  getAvailableOrganizations: vi.fn(),
  reset: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ logout: vi.fn() }) }))
vi.mock('@/stores/invitations', () => ({ useInvitationsStore: () => invitationsStore }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))

import { useUserStore } from '../user'
import type { IUser } from '../user.interfaces'

const user = { id: 'user-1' } as IUser

describe('user store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMocks.getMe.mockResolvedValue(user)
    organizationStore.getAvailableOrganizations.mockResolvedValue(undefined)
  })

  it('loads invitations before organizations', async () => {
    let resolveInvitations = () => {}
    invitationsStore.getInvitations.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveInvitations = resolve
      }),
    )
    const store = useUserStore()

    await store.loadUser()
    await vi.waitFor(() => expect(invitationsStore.getInvitations).toHaveBeenCalledOnce())
    expect(organizationStore.getAvailableOrganizations).not.toHaveBeenCalled()

    resolveInvitations()
    await vi.waitFor(() =>
      expect(organizationStore.getAvailableOrganizations).toHaveBeenCalledOnce(),
    )
  })

  it('loads organizations when invitations fail', async () => {
    invitationsStore.getInvitations.mockRejectedValue(new Error('unavailable'))
    const store = useUserStore()

    await store.loadUser()

    await vi.waitFor(() =>
      expect(organizationStore.getAvailableOrganizations).toHaveBeenCalledOnce(),
    )
  })
})
