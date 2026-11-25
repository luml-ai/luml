import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getInvitations: vi.fn(),
  getOwnershipTransfers: vi.fn(),
  acceptInvitation: vi.fn(),
  rejectInvitation: vi.fn(),
}))
const organizationStore = vi.hoisted(() => ({
  currentOrganization: null as { id: string } | null,
  getAvailableOrganizations: vi.fn(),
  switchOrganization: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))

import { useInvitationsStore } from '../invitations'
import type { Invitation, OwnershipTransfer } from '@/lib/api/api.interfaces'

const invitation = {
  id: 'invite-1',
  organization_id: 'organization-1',
} as Invitation
const ownershipTransfer = {
  id: 'transfer-1',
  organization_id: 'organization-2',
} as OwnershipTransfer

describe('invitations store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    organizationStore.currentOrganization = null
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
    expect(organizationStore.switchOrganization).toHaveBeenCalledWith(invitation.organization_id)
  })

  it('switches to the joined organization only after the organization list refreshes', async () => {
    apiMocks.acceptInvitation.mockResolvedValue(undefined)
    organizationStore.currentOrganization = { id: 'organization-a' }
    const calls: string[] = []
    organizationStore.getAvailableOrganizations.mockImplementation(async () => {
      calls.push('refresh')
    })
    organizationStore.switchOrganization.mockImplementation(async (id: string) => {
      calls.push(`switch:${id}`)
    })
    const store = useInvitationsStore()

    await store.acceptInvitation(invitation.id, invitation.organization_id)

    expect(calls).toEqual(['refresh', `switch:${invitation.organization_id}`])
  })

  it('does not switch again when the refresh already selected the joined organization', async () => {
    apiMocks.acceptInvitation.mockResolvedValue(undefined)
    organizationStore.getAvailableOrganizations.mockImplementation(async () => {
      organizationStore.currentOrganization = { id: invitation.organization_id }
    })
    const store = useInvitationsStore()

    await store.acceptInvitation(invitation.id, invitation.organization_id)

    expect(organizationStore.switchOrganization).not.toHaveBeenCalled()
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

  it('flags pending ownership transfers without organization invitations', async () => {
    apiMocks.getOwnershipTransfers.mockResolvedValue([ownershipTransfer])
    const store = useInvitationsStore()
    expect(store.hasPendingInvitations).toBe(false)

    await store.getOwnershipTransfers()

    expect(store.invitations).toEqual([])
    expect(store.ownershipTransfers).toEqual([ownershipTransfer])
    expect(store.hasPendingInvitations).toBe(true)
  })

  it('flags pending organization invitations without ownership transfers', () => {
    const store = useInvitationsStore()

    store.invitations = [invitation]

    expect(store.hasPendingInvitations).toBe(true)
  })

  it('keeps loaded ownership transfers when a reload fails', async () => {
    apiMocks.getOwnershipTransfers
      .mockResolvedValueOnce([ownershipTransfer])
      .mockRejectedValueOnce(new Error('unavailable'))
    const store = useInvitationsStore()
    await store.getOwnershipTransfers()

    await expect(store.getOwnershipTransfers()).rejects.toThrow('unavailable')

    expect(store.ownershipTransfers).toEqual([ownershipTransfer])
    expect(store.ownershipTransfersLoadError).toBe(true)
  })

  it('drops ownership transfers that arrive after a reset', async () => {
    let resolveTransfers: (value: OwnershipTransfer[]) => void = () => {}
    apiMocks.getOwnershipTransfers.mockReturnValue(
      new Promise<OwnershipTransfer[]>((resolve) => {
        resolveTransfers = resolve
      }),
    )
    const store = useInvitationsStore()
    const request = store.getOwnershipTransfers()

    store.reset()
    resolveTransfers([ownershipTransfer])
    await request

    expect(store.ownershipTransfers).toEqual([])
    expect(store.hasPendingInvitations).toBe(false)
  })
})
