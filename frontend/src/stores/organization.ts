import type {
  CreateOrganizationPayload,
  Invitation,
  Organization,
  OrganizationDetails,
  UpdateMemberPayload,
} from '@/lib/api/api.interfaces'
import { defineStore } from 'pinia'
import { api } from '@/lib/api'
import { ref } from 'vue'
import type { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { computed } from 'vue'

export const useOrganizationStore = defineStore('organization', () => {
  const availableOrganizations = ref<Organization[]>([])
  const organizationDetails = ref<OrganizationDetails | null>(null)
  const currentOrganizationId = ref<string | null>(null)
  const loading = ref(false)

  const currentOrganization = computed(() => {
    return (
      availableOrganizations.value.find(
        (organization) => organization.id === currentOrganizationId.value,
      ) || null
    )
  })

  function setLoading(value: boolean) {
    loading.value = value
  }

  async function getAvailableOrganizations() {
    const response = await api.getOrganizations()
    availableOrganizations.value = response
    await setInitialOrganization()
  }

  async function createOrganization(payload: CreateOrganizationPayload) {
    await api.createOrganization(payload)
    await getAvailableOrganizations()
  }

  async function updateOrganization(organizationId: string, payload: CreateOrganizationPayload) {
    const details = await api.updateOrganization(organizationId, payload)
    availableOrganizations.value = availableOrganizations.value.map((organization) => {
      return organization.id === organizationId
        ? { ...details, role: organization.role }
        : organization
    })
    organizationDetails.value = details
  }

  async function deleteOrganization(organizationId: string) {
    await api.deleteOrganization(organizationId)
    const organizationInLocalStorage = LocalStorageService.get('currentOrganizationId')
    if (organizationInLocalStorage && organizationInLocalStorage === organizationId) {
      LocalStorageService.remove('currentOrganizationId')
    }
    availableOrganizations.value = availableOrganizations.value.filter(
      (organization) => organization.id !== organizationId,
    )
    setInitialOrganization()
  }

  async function setCurrentOrganizationId(id: string) {
    currentOrganizationId.value = id
    LocalStorageService.set('currentOrganizationId', `${id}`)
  }

  async function getOrganizationDetails(id: string) {
    loading.value = true
    try {
      organizationDetails.value = await api.getOrganization(id)
    } finally {
      loading.value = false
    }
  }

  async function setInitialOrganization() {
    const organizationInStorage = LocalStorageService.get('currentOrganizationId')
    const organizationInStorageAvailable =
      organizationInStorage &&
      availableOrganizations.value?.find((org) => org.id === organizationInStorage)
    const organizationForSelect = organizationInStorageAvailable
      ? organizationInStorageAvailable.id
      : availableOrganizations.value?.[0]?.id
    if (!organizationForSelect) return
    await setCurrentOrganizationId(organizationForSelect)
  }

  function resetCurrentOrganization() {
    currentOrganizationId.value = null
  }

  async function updateMember(
    organizationId: string,
    memberId: string,
    payload: UpdateMemberPayload,
  ) {
    const info = await api.updateOrganizationMember(organizationId, memberId, payload)
    const currentOrganizationDetails = organizationDetails.value
    if (!currentOrganizationDetails) return
    currentOrganizationDetails.members = currentOrganizationDetails.members.map((member) => {
      if (member.id !== memberId) return member
      currentOrganizationDetails.members_by_role[member.role] =
        currentOrganizationDetails.members_by_role[member.role] - 1
      currentOrganizationDetails.members_by_role[info.role] =
        currentOrganizationDetails.members_by_role[info.role] + 1
      return info
    })
  }

  async function deleteMember(organizationId: string, memberId: string) {
    await api.deleteMemberFormOrganization(organizationId, memberId)
    if (!organizationDetails.value) return
    const members = organizationDetails.value.members.filter((member) => member.id !== memberId)
    organizationDetails.value = { ...organizationDetails.value, members: members }
  }

  function removeInviteFromCurrentOrganization(inviteId: string) {
    if (!organizationDetails.value) return
    organizationDetails.value = {
      ...organizationDetails.value,
      invites: organizationDetails.value.invites.filter((invite) => invite.id !== inviteId),
    }
  }

  function addInviteToCurrentOrganization(invite: Invitation) {
    organizationDetails.value?.invites.push(invite)
  }

  async function leaveOrganization(organizationId: string) {
    await api.leaveOrganization(organizationId)
    availableOrganizations.value = availableOrganizations.value.filter(
      (organization) => organization.id !== organizationId,
    )
  }

  function reset() {
    availableOrganizations.value = []
    resetCurrentOrganization()
  }

  return {
    availableOrganizations,
    currentOrganization,
    loading,
    organizationDetails,
    getAvailableOrganizations,
    createOrganization,
    updateOrganization,
    deleteOrganization,
    resetCurrentOrganization,
    deleteMember,
    updateMember,
    removeInviteFromCurrentOrganization,
    addInviteToCurrentOrganization,
    leaveOrganization,
    setCurrentOrganizationId,
    setLoading,
    getOrganizationDetails,
    reset,
  }
})
