import type { CreateInvitePayload, Invitation, OwnershipTransfer } from '@/lib/api/api.interfaces'
import { api } from '@/lib/api'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useOrganizationStore } from './organization'

export const useInvitationsStore = defineStore('invitations', () => {
  const organizationStore = useOrganizationStore()

  const invitations = ref<Invitation[]>([])
  const isLoading = ref(false)
  const isLoaded = ref(false)
  const loadError = ref(false)
  const ownershipTransfers = ref<OwnershipTransfer[]>([])
  const ownershipTransfersLoadError = ref(false)
  let invitationsRequestId = 0
  let ownershipTransfersRequestId = 0

  const hasPendingInvitations = computed(
    () => invitations.value.length > 0 || ownershipTransfers.value.length > 0,
  )

  async function getInvitations() {
    const requestId = ++invitationsRequestId
    isLoading.value = true
    loadError.value = false

    try {
      const response = await api.getInvitations()
      if (requestId === invitationsRequestId) invitations.value = response
    } catch (error) {
      if (requestId === invitationsRequestId) {
        invitations.value = []
        loadError.value = true
      }
      throw error
    } finally {
      if (requestId === invitationsRequestId) {
        isLoading.value = false
        isLoaded.value = true
      }
    }
  }

  async function getOwnershipTransfers() {
    const requestId = ++ownershipTransfersRequestId
    try {
      const response = await api.getOwnershipTransfers()
      if (requestId !== ownershipTransfersRequestId) return
      ownershipTransfers.value = response
      ownershipTransfersLoadError.value = false
    } catch (error) {
      if (requestId === ownershipTransfersRequestId) ownershipTransfersLoadError.value = true
      throw error
    }
  }

  async function acceptInvitation(inviteId: string, organizationId: string) {
    await api.acceptInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
    await organizationStore.getAvailableOrganizations()
    if (organizationStore.currentOrganization?.id !== organizationId) {
      await organizationStore.switchOrganization(organizationId)
    }
  }

  async function rejectInvitation(inviteId: string) {
    await api.rejectInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
  }

  async function createInvite(organizationId: string, payload: CreateInvitePayload) {
    return api.createInvite(organizationId, payload)
  }

  async function cancelInvite(organizationId: string, inviteId: string) {
    return api.cancelInvitation(organizationId, inviteId)
  }

  function reset() {
    invitationsRequestId++
    invitations.value = []
    isLoading.value = false
    isLoaded.value = false
    loadError.value = false
    ownershipTransfersRequestId++
    ownershipTransfers.value = []
    ownershipTransfersLoadError.value = false
  }

  return {
    invitations,
    isLoading,
    isLoaded,
    loadError,
    ownershipTransfers,
    ownershipTransfersLoadError,
    hasPendingInvitations,
    getInvitations,
    getOwnershipTransfers,
    acceptInvitation,
    rejectInvitation,
    createInvite,
    cancelInvite,
    reset,
  }
})
