import type {
  CreateOrganizationPayload,
  Invitation,
  Organization,
  OrganizationDetails,
  UpdateMemberPayload,
} from '@/lib/api/DataforceApi.interfaces'
import { defineStore } from 'pinia'
import { dataforceApi } from '@/lib/api'
import { ref } from 'vue'
import type { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { computed } from 'vue'

export const useOrganizationStore = defineStore('organization', () => {
  const availableOrganizations = ref<Organization[]>([])
  const organizationDetails = ref<OrganizationDetails | null>(null)
  const currentOrganizationId = ref<number | null>(null)
  const loading = ref(false)

  const currentOrganization = computed(() => {
    return availableOrganizations.value.find(organization => organization.id === currentOrganizationId.value) || null
  })

  function setLoading(value: boolean) {
    loading.value = value
  }

  async function getAvailableOrganizations() {
    const response = await dataforceApi.getOrganizations()
    availableOrganizations.value = response
    await setInitialOrganization()
  }

  async function createOrganization(payload: CreateOrganizationPayload) {
    await dataforceApi.createOrganization(payload)
    await getAvailableOrganizations()
  }

  async function updateOrganization(organizationId: number, payload: CreateOrganizationPayload) {
    const details = await dataforceApi.updateOrganization(organizationId, payload)
    availableOrganizations.value = availableOrganizations.value.map(organization => {
      return organization.id === organizationId ? { ...details, role: organization.role } : organization
    })
    organizationDetails.value = details
  }

  async function deleteOrganization(organizationId: number) {
    await dataforceApi.deleteOrganization(organizationId)
    const organizationInLocalStorage = LocalStorageService.get('dataforce:currentOrganizationId')
    if (organizationInLocalStorage && +organizationInLocalStorage === organizationId) {
      LocalStorageService.remove('dataforce:currentOrganizationId')
    }
    availableOrganizations.value = availableOrganizations.value.filter(
      (organization) => organization.id !== organizationId,
    )
    setInitialOrganization()
  }

  async function setCurrentOrganizationId(id: number) {
    currentOrganizationId.value = id
    LocalStorageService.set('dataforce:currentOrganizationId', `${id}`)
  }

  async function getOrganizationDetails(id: number) {
    loading.value = true
    try {
      organizationDetails.value = await dataforceApi.getOrganization(id)
    } finally {
      loading.value = false
    }
  }

  async function setInitialOrganization() {
    const organizationInStorage = LocalStorageService.get('dataforce:currentOrganizationId')
    const organizationInStorageAvailable =
      organizationInStorage &&
      availableOrganizations.value?.find((org) => org.id === +organizationInStorage)
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
    organizationId: number,
    memberId: number,
    payload: UpdateMemberPayload,
  ) {
    const info = await dataforceApi.updateOrganizationMember(organizationId, memberId, payload)
    const currentOrganizationDetails = organizationDetails.value;
    if (!currentOrganizationDetails) return;
    currentOrganizationDetails.members = currentOrganizationDetails.members.map(member => {
      if (member.id !== memberId) return member;
      currentOrganizationDetails.members_by_role[member.role] = currentOrganizationDetails.members_by_role[member.role] - 1;
      currentOrganizationDetails.members_by_role[info.role] = currentOrganizationDetails.members_by_role[info.role] + 1;
      return info;
    })
  }

  async function deleteMember(organizationId: number, memberId: number) {
    await dataforceApi.deleteMemberFormOrganization(organizationId, memberId)
    if (!organizationDetails.value) return
    const members = organizationDetails.value.members.filter((member) => member.id !== memberId)
    organizationDetails.value = { ...organizationDetails.value, members: members }
  }

  function removeInviteFromCurrentOrganization(inviteId: number) {
    if (!organizationDetails.value) return
    organizationDetails.value = {
      ...organizationDetails.value,
      invites: organizationDetails.value.invites.filter((invite) => invite.id !== inviteId),
    }
  }

  function addInviteToCurrentOrganization(invite: Invitation) {
    organizationDetails.value?.invites.push(invite)
  }

  async function leaveOrganization(organizationId: number) {
    await dataforceApi.leaveOrganization(organizationId)
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
