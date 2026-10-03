import { api } from '@/lib/api'
import type { Flow } from '@/lib/api/flows/interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFlowsStore = defineStore('flows', () => {
  const flowsList = ref<Flow[]>([])

  async function loadFlows(organizationId: string, orbitId: string) {
    flowsList.value = await api.flows.getList(organizationId, orbitId)
  }

  async function removeFlow(organizationId: string, orbitId: string, flowId: string) {
    await api.flows.remove(organizationId, orbitId, flowId)
    flowsList.value = flowsList.value.filter((flow) => flow.id !== flowId)
  }

  function reset() {
    flowsList.value = []
  }

  return {
    flowsList,
    loadFlows,
    removeFlow,
    reset,
  }
})
