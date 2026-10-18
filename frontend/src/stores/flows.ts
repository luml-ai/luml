import { api } from '@/lib/api'
import type { Flow } from '@/lib/api/flows/interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFlowsStore = defineStore('flows', () => {
  const flowsList = ref<Flow[]>([])
  // Only the latest load may set the list, so a slow answer for another orbit
  // or from before a removal cannot overwrite a newer state.
  let loadGeneration = 0

  async function loadFlows(organizationId: string, orbitId: string) {
    const generation = ++loadGeneration
    const flows = await api.flows.getList(organizationId, orbitId)
    if (generation === loadGeneration) flowsList.value = flows
  }

  async function removeFlow(organizationId: string, orbitId: string, flowId: string) {
    await api.flows.remove(organizationId, orbitId, flowId)
    loadGeneration++
    flowsList.value = flowsList.value.filter((flow) => flow.id !== flowId)
  }

  function reset() {
    loadGeneration++
    flowsList.value = []
  }

  return {
    flowsList,
    loadFlows,
    removeFlow,
    reset,
  }
})
