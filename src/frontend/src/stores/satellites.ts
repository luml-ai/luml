import { api } from '@/lib/api'
import type { CreateSatellitePayload, Satellite } from '@/lib/api/satellites/interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSatellitesStore = defineStore('satellites', () => {
  const satellitesList = ref<Satellite[]>([])
  const creatorVisible = ref(false)

  async function createSatellite(
    organizationId: string,
    orbitId: string,
    payload: CreateSatellitePayload,
  ) {
    const data = await api.satellites.create(organizationId, orbitId, payload)
    satellitesList.value.push(data.satellite)
    return data
  }

  async function loadSatellites(organizationId: string, orbitId: string) {
    return api.satellites.getList(organizationId, orbitId)
  }

  function setList(list: Satellite[]) {
    satellitesList.value = list
  }

  async function deleteSatellite(organizationId: string, orbitId: string, satelliteId: string) {
    await api.satellites.delete(organizationId, orbitId, satelliteId)
    setList(satellitesList.value.filter((satellite) => satellite.id !== satelliteId))
  }

  async function updateSatellite(
    organizationId: string,
    orbitId: string,
    satelliteId: string,
    payload: CreateSatellitePayload,
  ) {
    const newData = await api.satellites.update(organizationId, orbitId, satelliteId, payload)
    const newList = satellitesList.value.map((satellite) => {
      if (satellite.id === newData.id) return newData
      else return satellite
    })
    setList(newList)
  }

  async function regenerateApiKey(organizationId: string, orbitId: string, satelliteId: string) {
    return api.satellites.regenerateApiKye(organizationId, orbitId, satelliteId)
  }

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  function reset() {
    satellitesList.value = []
  }

  async function getSatellite(organizationId: string, orbitId: string, satelliteId: string) {
    const existingSatellite = satellitesList.value.find((satellite) => satellite.id === satelliteId)
    if (existingSatellite) {
      return existingSatellite
    }
    const satellite = await api.satellites.getItem(organizationId, orbitId, satelliteId)
    return satellite
  }

  return {
    satellitesList,
    creatorVisible,
    createSatellite,
    loadSatellites,
    setList,
    deleteSatellite,
    updateSatellite,
    regenerateApiKey,
    showCreator,
    hideCreator,
    reset,
    getSatellite,
  }
})
