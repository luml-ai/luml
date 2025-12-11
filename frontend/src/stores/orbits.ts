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

export const useOrbitsStore = defineStore('orbit', () => {
  const orbitsList = ref<Orbit[]>([])
  const currentOrbitDetails = ref<OrbitDetails | null>(null)

  const getCurrentOrbitPermissions = computed(() => currentOrbitDetails.value?.permissions)

  async function loadOrbitsList(organizationId: string) {
    orbitsList.value = await api.getOrganizationOrbits(organizationId)
  }

  async function createOrbit(organizationId: string, payload: CreateOrbitPayload) {
    const orbit = await api.createOrbit(organizationId, payload)
    orbitsList.value.push(orbit)
  }

  async function updateOrbit(organizationId: string, payload: UpdateOrbitPayload) {
    const orbit = await api.updateOrbit(organizationId, payload)
    orbitsList.value = orbitsList.value.map((savedOrbit) => {
      if (savedOrbit.id !== orbit.id) return savedOrbit
      return orbit
    })
  }

  async function deleteOrbit(organizationId: string, orbitId: string) {
    await api.deleteOrbit(organizationId, orbitId)
    orbitsList.value = orbitsList.value.filter((orbit) => orbit.id !== orbitId)
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
    currentOrbitDetails.value = null
  }

  return {
    orbitsList,
    currentOrbitDetails,
    getCurrentOrbitPermissions,
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
