import type { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { api } from '@/lib/api'
import type {
  AddMemberToOrbitPayload,
  CreateOrbitPayload,
  Orbit,
  OrbitDetails,
  UpdateOrbitPayload,
} from '@/lib/api/api.interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useOrganizationStore } from './organization'

export const useOrbitsStore = defineStore('orbit', () => {
  const organizationStore = useOrganizationStore()

  const orbitsList = ref<Orbit[]>([])
  const currentOrbitId = ref<string | null>(null)
  const currentOrbitDetails = ref<OrbitDetails | null>(null)
  const isLoadingOrbitDetails = ref(false)

  const currentOrbit = computed(
    () => orbitsList.value.find((o) => o.id === currentOrbitId.value) ?? null,
  )
  const hasCurrentOrbit = computed(() => currentOrbitId.value !== null)
  const getCurrentOrbitPermissions = computed(() => currentOrbitDetails.value?.permissions)

  function setCurrentOrbitId(id: string | null, orgId?: string) {
    currentOrbitId.value = id
    currentOrbitDetails.value = null

    if (id) {
      const resolvedOrgId = orgId ?? organizationStore.currentOrganization?.id
      if (resolvedOrgId) {
        loadOrbitDetails(resolvedOrgId, id)
      }
    }
  }

  async function loadOrbitDetails(orgId: string, orbitId: string) {
    isLoadingOrbitDetails.value = true

    try {
      const details = await getOrbitDetails(orgId, orbitId)
      if (currentOrbitId.value !== orbitId) return
      currentOrbitDetails.value = details
    } catch (e) {
      console.error('Failed to load orbit details', e)
      if (currentOrbitId.value !== orbitId) return
      currentOrbitDetails.value = null
    } finally {
      if (currentOrbitId.value === orbitId) {
        isLoadingOrbitDetails.value = false
      }
    }
  }

  async function loadOrbitsList(organizationId: string) {
    orbitsList.value = await api.getOrganizationOrbits(organizationId)
  }

  async function createOrbit(organizationId: string, payload: CreateOrbitPayload) {
    const orbit = await api.createOrbit(organizationId, payload)
    orbitsList.value.push(orbit)
    if (!organizationStore.organizationDetails) return orbit
    organizationStore.organizationDetails.orbits.push(orbit)
    return orbit
  }

  async function updateOrbit(organizationId: string, payload: UpdateOrbitPayload) {
    const orbit = await api.updateOrbit(organizationId, payload)
    orbitsList.value = updatedOrbitsList(orbitsList.value, orbit)

    if (!organizationStore.organizationDetails) return
    organizationStore.organizationDetails.orbits = updatedOrbitsList(
      organizationStore.organizationDetails.orbits,
      orbit,
    )
    if (currentOrbitId.value === orbit.id) {
      try {
        const details = await getOrbitDetails(organizationId, orbit.id)
        if (currentOrbitId.value === orbit.id) {
          currentOrbitDetails.value = details
        }
      } catch (e) {
        console.error('Failed to reload orbit details', e)
      }
    }
  }

  function updatedOrbitsList(list: Orbit[], orbit: Orbit) {
    return list.map((savedOrbit) => {
      if (savedOrbit.id !== orbit.id) return savedOrbit
      return orbit
    })
  }

  async function deleteOrbit(organizationId: string, orbitId: string) {
    await api.deleteOrbit(organizationId, orbitId)
    orbitsList.value = orbitsList.value.filter((orbit) => orbit.id !== orbitId)

    if (currentOrbitId.value === orbitId) {
      currentOrbitId.value = null
      currentOrbitDetails.value = null
    }
  }

  async function addMemberToOrbit(organizationId: string, payload: AddMemberToOrbitPayload) {
    return api.addMemberToOrbit(organizationId, payload)
  }

  async function getOrbitDetails(organizationId: string, orbitId: string) {
    return api.getOrbitDetails(organizationId, orbitId)
  }

  async function deleteMember(organizationId: string, orbitId: string, memberId: string) {
    return api.deleteOrbitMember(organizationId, orbitId, memberId)
  }

  async function updateMember(
    organizationId: string,
    orbitId: string,
    data: { id: string; role: OrbitRoleEnum },
  ) {
    return api.updateOrbitMember(organizationId, orbitId, data)
  }

  function setCurrentOrbitDetails(details: OrbitDetails | null) {
    currentOrbitDetails.value = details
  }

  function reset() {
    orbitsList.value = []
    currentOrbitId.value = null
    currentOrbitDetails.value = null
    isLoadingOrbitDetails.value = false
  }

  return {
    orbitsList,
    currentOrbit,
    currentOrbitId,
    currentOrbitDetails,
    isLoadingOrbitDetails,
    hasCurrentOrbit,
    getCurrentOrbitPermissions,
    setCurrentOrbitId,
    loadOrbitDetails,
    createOrbit,
    addMemberToOrbit,
    getOrbitDetails,
    deleteMember,
    updateMember,
    loadOrbitsList,
    updateOrbit,
    deleteOrbit,
    setCurrentOrbitDetails,
    reset,
  }
})
