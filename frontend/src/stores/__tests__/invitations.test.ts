import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
  rejectInvitation: vi.fn(),
}))
const organizationStore = vi.hoisted(() => ({
  getAvailableOrganizations: vi.fn(),
  setCurrentOrganizationId: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))

import { useInvitationsStore } from '../invitations'
import type { Invitation } from '@/lib/api/api.interfaces'

const invitation = {
  id: 'invite-1',
  organization_id: 'organization-1',
} as Invitation

describe('invitations store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('tracks a successful invitation load', async () => {
    apiMocks.getInvitations.mockResolvedValue([invitation])
    const store = useInvitationsStore()

    const request = store.getInvitations()
    expect(store.isLoading).toBe(true)
    expect(store.isLoaded).toBe(false)

    await request

    expect(store.invitations).toEqual([invitation])
    expect(store.isLoading).toBe(false)
    expect(store.isLoaded).toBe(true)
    expect(store.loadError).toBe(false)
  })

  it('distinguishes a failed load from an empty result', async () => {
    apiMocks.getInvitations.mockRejectedValue(new Error('unavailable'))
    const store = useInvitationsStore()

    await expect(store.getInvitations()).rejects.toThrow('unavailable')

    expect(store.invitations).toEqual([])
    expect(store.isLoading).toBe(false)
    expect(store.isLoaded).toBe(true)
    expect(store.loadError).toBe(true)
  })

  it('removes an accepted invitation after dependent data refreshes', async () => {
    apiMocks.acceptInvitation.mockResolvedValue(undefined)
    organizationStore.getAvailableOrganizations.mockResolvedValue(undefined)
    const store = useInvitationsStore()
    store.invitations = [invitation]

    await store.acceptInvitation(invitation.id, invitation.organization_id)

    expect(store.invitations).toEqual([])
    expect(organizationStore.setCurrentOrganizationId).toHaveBeenCalledWith(
      invitation.organization_id,
    )
  })

  it('keeps an invitation when accepting it fails', async () => {
    apiMocks.acceptInvitation.mockRejectedValue(new Error('unavailable'))
    const store = useInvitationsStore()
    store.invitations = [invitation]

    await expect(store.acceptInvitation(invitation.id, invitation.organization_id)).rejects.toThrow(
      'unavailable',
    )

    expect(store.invitations).toEqual([invitation])
  })

  it('removes a declined invitation only after success', async () => {
    apiMocks.rejectInvitation.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error())
    const store = useInvitationsStore()
    store.invitations = [invitation]

    await store.rejectInvitation(invitation.id)
    expect(store.invitations).toEqual([])

    store.invitations = [invitation]
    await expect(store.rejectInvitation(invitation.id)).rejects.toThrow()
    expect(store.invitations).toEqual([invitation])
  })
})
