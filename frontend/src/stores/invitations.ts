import type { CreateInvitePayload, Invitation } from '@/lib/api/DataforceApi.interfaces'
import { dataforceApi } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useOrganizationStore } from './organization'

export const useInvitationsStore = defineStore('invitations', () => {
  const organizationStore = useOrganizationStore()

  const invitations = ref<Invitation[]>([])

  async function getInvitations() {
    invitations.value = await dataforceApi.getInvitations()
  }

  async function acceptInvitation(inviteId: number, organizationId: number) {
    await dataforceApi.acceptInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
    await organizationStore.getAvailableOrganizations()
    organizationStore.setCurrentOrganizationId(organizationId)
  }

  async function rejectInvitation(inviteId: number) {
    await dataforceApi.rejectInvitation(inviteId)
    invitations.value = invitations.value.filter((invitation) => invitation.id !== inviteId)
  }

  async function createInvite(payload: CreateInvitePayload) {
    return dataforceApi.createInvite(payload.organization_id, payload)
  }

  async function cancelInvite(organizationId: number, inviteId: number) {
    return dataforceApi.cancelInvitation(organizationId, inviteId)
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
