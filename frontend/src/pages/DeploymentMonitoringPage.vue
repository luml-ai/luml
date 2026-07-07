<template>
  <div class="monitoring-page">
    <Breadcrumb :model="breadcrumbs" :pt="{ root: { style: 'padding-left: 0' } }">
      <template #item="{ item, props: itemProps }">
        <RouterLink v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
          <a :href="href" v-bind="itemProps.action" @click="navigate">{{ item.label }}</a>
        </RouterLink>
        <span v-else v-bind="itemProps.action">{{ item.label }}</span>
      </template>
    </Breadcrumb>

    <UiPageLoader v-if="store.status === 'loading' || store.status === 'idle'" />

    <MonitoringStatePanel
      v-else-if="store.status === 'disabled'"
      testid="monitoring-disabled"
      title="Monitoring unavailable"
      :description="disabledDescription"
    >
      <template #icon><PowerOff :size="40" /></template>
    </MonitoringStatePanel>

    <MonitoringStatePanel
      v-else-if="store.status === 'unavailable'"
      testid="monitoring-unavailable"
      title="Monitoring is unreachable"
      description="The Satellite dashboard could not be launched. No monitoring data is proxied through the Platform."
    >
      <template #icon><TriangleAlert :size="40" /></template>
      <template #action>
        <Button label="Try again" data-testid="monitoring-retry" @click="relaunch">
          <template #icon><RefreshCw :size="14" /></template>
        </Button>
      </template>
    </MonitoringStatePanel>

    <MonitoringStatePanel
      v-else-if="store.status === 'expired'"
      testid="monitoring-expired"
      title="Session expired"
      description="Your monitoring session has expired. Re-launch to open the dashboard again."
    >
      <template #icon><Clock :size="40" /></template>
      <template #action>
        <Button label="Re-launch" data-testid="monitoring-relaunch" @click="relaunch">
          <template #icon><RefreshCw :size="14" /></template>
        </Button>
      </template>
    </MonitoringStatePanel>

    <iframe
      v-else-if="store.status === 'active' && store.launchUrl"
      :src="store.launchUrl"
      class="monitoring-frame"
      title="Deployment monitoring dashboard"
      data-testid="monitoring-iframe"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Breadcrumb, Button } from 'primevue'
import { PowerOff, TriangleAlert, Clock, RefreshCw } from 'lucide-vue-next'
import { useMonitoringStore, MONITORING_SESSION_EXPIRED_MESSAGE } from '@/stores/monitoring'
import { MonitoringIneligibilityReason } from '@/lib/api/monitoring/interfaces'
import MonitoringStatePanel from '@/components/deployments/monitoring/MonitoringStatePanel.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const route = useRoute()
const store = useMonitoringStore()

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
  return { organizationId, orbitId, deploymentId }
})

const breadcrumbs = computed(() => [
  {
    label: 'Deployments',
    route: {
      name: 'orbit-deployments',
      params: { organizationId: requestInfo.value.organizationId, id: requestInfo.value.orbitId },
    },
  },
  { label: 'Monitoring' },
])

const disabledDescription = computed(() => {
  if (store.reason === MonitoringIneligibilityReason.capability_missing) {
    return 'The Satellite hosting this deployment does not advertise the monitoring capability.'
  }
  return 'Monitoring is turned off for this deployment. Enable monitoring to view the dashboard.'
})

function relaunch() {
  const { organizationId, orbitId, deploymentId } = requestInfo.value
  store.launch(organizationId, orbitId, deploymentId)
}

function onMessage(event: MessageEvent) {
  if (!store.satelliteOrigin || event.origin !== store.satelliteOrigin) return
  if (event.data?.type === MONITORING_SESSION_EXPIRED_MESSAGE) {
    store.markExpired()
  }
}

onMounted(() => {
  window.addEventListener('message', onMessage)
  relaunch()
})

onUnmounted(() => {
  window.removeEventListener('message', onMessage)
  store.reset()
})
</script>

<style scoped>
.monitoring-page {
  padding-top: 18px;
}

.monitoring-frame {
  width: 100%;
  height: calc(100vh - 160px);
  border: none;
  border-radius: 8px;
  background-color: var(--p-card-background);
}
</style>
