import type {
  CreateDeploymentPayload,
  Deployment,
  UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'
import { api } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDeploymentsStore = defineStore('deployments', () => {
  const deployments = ref<Deployment[]>([])
  const creatorVisible = ref(false)

  async function createDeployment(
    organizationId: string,
    orbitId: string,
    payload: CreateDeploymentPayload,
  ) {
    const newDeployment = await api.deployments.create(organizationId, orbitId, payload)
    deployments.value.push(newDeployment)
  }

  function getDeployments(organizationId: string, orbitId: string) {
    return api.deployments.getList(organizationId, orbitId)
  }

  function setDeployments(data: Deployment[]) {
    deployments.value = data
  }

  function reset() {
    deployments.value = []
  }

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  async function deleteDeployment(organizationId: string, orbitId: string, deploymentId: string) {
    const updatedDeployment = await api.deployments.deleteDeployment(
      organizationId,
      orbitId,
      deploymentId,
    )
    deployments.value = deployments.value.map((deployment) =>
      deployment.id === updatedDeployment.id ? updatedDeployment : deployment,
    )
  }

  async function update(
    organizationId: string,
    orbitId: string,
    deploymentId: string,
    payload: UpdateDeploymentPayload,
  ) {
    const newDeployment = await api.deployments.update(
      organizationId,
      orbitId,
      deploymentId,
      payload,
    )
    deployments.value = deployments.value.map((deployment) => {
      return deployment.id === newDeployment.id ? newDeployment : deployment
    })
  }

  async function getDeployment(organizationId: string, orbitId: string, deploymentId: string) {
    const existingDeployment = deployments.value.find(
      (deployment) => deployment.id === deploymentId,
    )
    if (existingDeployment) {
      return existingDeployment
    }
    const deployment = await api.deployments.getDeployment(organizationId, orbitId, deploymentId)
    return deployment
  }

  async function forceDeleteDeployment(
    organizationId: string,
    orbitId: string,
    deploymentId: string,
  ) {
    await api.deployments.forceDeleteDeployment(organizationId, orbitId, deploymentId)
    deployments.value = deployments.value.filter((deployment) => deployment.id !== deploymentId)
  }

  return {
    deployments,
    creatorVisible,
    createDeployment,
    getDeployments,
    setDeployments,
    reset,
    showCreator,
    hideCreator,
    deleteDeployment,
    update,
    getDeployment,
    forceDeleteDeployment,
  }
})
