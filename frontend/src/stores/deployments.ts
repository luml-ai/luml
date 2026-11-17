import type {
  CreateDeploymentPayload,
  Deployment,
  DeploymentBatchAction,
  DeploymentsBatchResponse,
  UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'
import { DeploymentStatusEnum } from '@/lib/api/deployments/interfaces'
import { api } from '@/lib/api'
import { useSatellitesStore } from '@/stores/satellites'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDeploymentsStore = defineStore('deployments', () => {
  const deployments = ref<Deployment[]>([])
  const creatorVisible = ref(false)

  async function wakeSatellite(organizationId: string, orbitId: string, satelliteId: string) {
    try {
      const satellite = await useSatellitesStore().getSatellite(
        organizationId,
        orbitId,
        satelliteId,
      )
      if (satellite.base_url && satellite.present_capabilities.includes('wake')) {
        await fetch(`${satellite.base_url.replace(/\/$/, '')}/wake`, {
          method: 'POST',
          mode: 'no-cors',
          keepalive: true,
        })
      }
    } catch {
      // wake is a hint; the scheduled poll will pick up the task
    }
  }

  async function createDeployment(
    organizationId: string,
    orbitId: string,
    payload: CreateDeploymentPayload,
  ) {
    const newDeployment = await api.deployments.create(organizationId, orbitId, payload)
    deployments.value.push(newDeployment)
    void wakeSatellite(organizationId, orbitId, newDeployment.satellite_id)
  }

  function getDeployments(organizationId: string, orbitId: string) {
    return api.deployments.getList(organizationId, orbitId)
  }

  function setDeployments(data: Deployment[]) {
    deployments.value = data
  }

  function reset() {
    deployments.value = []
    creatorVisible.value = false
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
    void wakeSatellite(organizationId, orbitId, updatedDeployment.satellite_id)
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
    void wakeSatellite(organizationId, orbitId, newDeployment.satellite_id)
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

  async function batchAction(
    organizationId: string,
    orbitId: string,
    deploymentIds: string[],
    action: DeploymentBatchAction,
  ): Promise<DeploymentsBatchResponse> {
    const ids = [...new Set(deploymentIds)]
    const woken = new Set<string>()
    const result: DeploymentsBatchResponse = { succeeded: [], failed: [] }
    for (let offset = 0; offset < ids.length; offset += 100) {
      const batch = ids.slice(offset, offset + 100)
      try {
        const response = await api.deployments.batchAction(organizationId, orbitId, batch, action)
        result.succeeded.push(...response.succeeded)
        result.failed.push(...response.failed)
        const succeeded = new Set(response.succeeded)
        for (const deployment of deployments.value) {
          if (succeeded.has(deployment.id) && !woken.has(deployment.satellite_id)) {
            woken.add(deployment.satellite_id)
            void wakeSatellite(organizationId, orbitId, deployment.satellite_id)
          }
        }
        deployments.value =
          action === 'delete'
            ? deployments.value.filter(({ id }) => !succeeded.has(id))
            : deployments.value.map((deployment) =>
                succeeded.has(deployment.id)
                  ? { ...deployment, status: DeploymentStatusEnum.deletion_pending }
                  : deployment,
              )
      } catch {
        result.failed.push(
          ...batch.map((id) => ({
            deployment_id: id,
            name: deployments.value.find((deployment) => deployment.id === id)?.name ?? null,
            reason: 'request_error',
            message: 'Outcome not confirmed. Refresh the table before retrying.',
          })),
        )
      }
    }
    return result
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
    batchAction,
  }
})
