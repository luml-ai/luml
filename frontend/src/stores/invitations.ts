import type { CreateInvitePayload, Invitation } from '@/lib/api/api.interfaces'
import { api } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useOrganizationStore } from './organization'

export const useInvitationsStore = defineStore('invitations', () => {
  const organizationStore = useOrganizationStore()

  const invitations = ref<Invitation[]>([])

  async function getInvitations() {
    invitations.value = await api.getInvitations()
  }

  async function acceptInvitation(inviteId: string, organizationId: string) {
    await api.acceptInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
    await organizationStore.getAvailableOrganizations()
    organizationStore.setCurrentOrganizationId(organizationId)
  }

  async function rejectInvitation(inviteId: string) {
    await api.rejectInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
  }

  async function createInvite(payload: CreateInvitePayload) {
    return api.createInvite(payload.organization_id, payload)
  }

  async function cancelInvite(organizationId: string, inviteId: string) {
    return api.cancelInvitation(organizationId, inviteId)
  }

  function reset() {
    invitations.value = []
  }

  return {
    invitations,
    getInvitations,
    acceptInvitation,
    rejectInvitation,
    createInvite,
    cancelInvite,
    reset,
  }
})
