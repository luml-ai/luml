<template>
  <div class="deployment-schema-page">
    <UiPageLoader v-if="loading" />
    <OpenApi v-else-if="schema && serverUrl" :content="schema" :server-url="serverUrl" />
    <Ui404 v-else />
  </div>
</template>

<script setup lang="ts">
import type { Deployment } from '@/lib/api/deployments/interfaces'
import { computed, onMounted, ref } from 'vue'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useRoute } from 'vue-router'
import { useDeploymentsStore } from '@/stores/deployments'
import { useSatellitesStore } from '@/stores/satellites'
import OpenApi from '../components/openapi/OpenApi.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import Ui404 from '@/components/ui/Ui404.vue'

const toast = useToast()
const route = useRoute()
const deploymentsStore = useDeploymentsStore()
const satellitesStore = useSatellitesStore()

const schema = ref<object | null>(null)
const serverUrl = ref<string | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const deployment = await deploymentsStore.getDeployment(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.deploymentId,
    )
    if (!deployment) {
      throw new Error('Deployment was not found')
    }
    schema.value = getSchema(deployment)
    serverUrl.value = await getServerUrl(deployment)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to load deployment schema')))
  } finally {
    loading.value = false
  }
})

const requestInfo = computed(() => {
  const organizationId = route.params.organizationId
  const orbitId = route.params.id
  const deploymentId = route.params.deploymentId
  if (typeof organizationId !== 'string') {
    throw new Error('Organization ID is required')
  }
  if (typeof orbitId !== 'string') {
    throw new Error('Orbit ID is required')
  }
  if (typeof deploymentId !== 'string') {
    throw new Error('Deployment ID is required')
  }
  return {
    organizationId,
    orbitId,
    deploymentId,
  }
})

function getSchema(deployment: Deployment) {
  const schemas = deployment.schemas
  if (!schemas || !Object.keys(schemas).length) {
    throw new Error('Deployment schemas were not found')
  }
  return schemas
}

async function getSatellite(deployment: Deployment) {
  const satelliteId = deployment.satellite_id
  const satellite = await satellitesStore.getSatellite(
    requestInfo.value.organizationId,
    requestInfo.value.orbitId,
    satelliteId,
  )
  if (!satellite) {
    throw new Error('Satellite was not found')
  }
  return satellite
}

async function getServerUrl(deployment: Deployment) {
  const satellite = await getSatellite(deployment)
  return satellite.base_url
}
</script>

<style scoped>
.deployment-schema-page {
  margin: 0 -100px;
}
</style>
