<template>
  <div class="page-header">
    <div class="page-header__left">
      <ChartSpline :size="20" class="page-header__icon" />
      <router-link :to="{ name: 'orbit-flow' }" class="page-header__back">Flow</router-link>
      <span>/</span>
      <h1 class="page-header__title">{{ session?.name ?? sessionId }}</h1>
    </div>
    <div v-if="session?.status === LiveSessionStatusEnum.live" class="page-header__actions">
      <Button
        label="Open in new tab"
        severity="secondary"
        variant="outlined"
        data-testid="open-in-new-tab"
        @click="openInNewTab"
      >
        <template #icon><ExternalLink :size="14" /></template>
      </Button>
      <Button
        label="Stop session"
        severity="danger"
        variant="outlined"
        :loading="stopping"
        data-testid="stop-session"
        @click="stopSession"
      >
        <template #icon><Square :size="14" /></template>
      </Button>
    </div>
  </div>

  <UiPageLoader v-if="loading" />

  <MonitoringStatePanel
    v-else-if="notConfigured"
    testid="not-configured"
    title="Live sessions are not set up"
    description="Live sessions are not set up in this deployment."
  >
    <template #icon><TriangleAlert :size="40" /></template>
  </MonitoringStatePanel>

  <MonitoringStatePanel
    v-else-if="session?.status === LiveSessionStatusEnum.ended"
    testid="session-ended"
    title="The session has ended"
    description="Start the agent again to create a new session."
  >
    <template #icon><PowerOff :size="40" /></template>
  </MonitoringStatePanel>

  <MonitoringStatePanel
    v-else-if="session?.status === LiveSessionStatusEnum.disconnected"
    testid="session-disconnected"
    title="The session is disconnected"
    :description="disconnectedDescription"
  >
    <template #icon><Unplug :size="40" /></template>
  </MonitoringStatePanel>

  <MonitoringStatePanel
    v-else-if="frameBlocked"
    testid="frame-blocked"
    title="The session cannot be shown here"
    description="Your browser does not keep the session's cookie inside this page. Open the session in a new tab instead."
  >
    <template #icon><TriangleAlert :size="40" /></template>
    <template #action>
      <Button label="Open in new tab" data-testid="frame-blocked-open" @click="openInNewTab">
        <template #icon><ExternalLink :size="14" /></template>
      </Button>
    </template>
  </MonitoringStatePanel>

  <!-- `credentialless` keeps the cross-origin isolated app able to embed the relay's pages. -->
  <iframe
    v-else-if="frameUrl"
    :src="frameUrl"
    credentialless
    class="session-frame"
    title="Live session"
    data-testid="session-frame"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Button, useToast } from 'primevue'
import { ChartSpline, ExternalLink, PowerOff, Square, TriangleAlert, Unplug } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { LiveSessionStatusEnum, type LiveSession } from '@/lib/api/live-sessions/interfaces'
import {
  LIVE_SESSION_ACCESS_NEEDED_MESSAGE,
  isLiveSessionsNotConfigured,
} from '@/stores/live-sessions'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import MonitoringStatePanel from '@/components/deployments/monitoring/MonitoringStatePanel.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const route = useRoute()
const toast = useToast()

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)
const sessionId = computed(() => route.params.sessionId as string)

const session = ref<LiveSession | null>(null)
const loading = ref(true)
const notConfigured = ref(false)
const stopping = ref(false)
const frameUrl = ref<string | null>(null)
const relayOrigin = ref<string | null>(null)
const frameBlocked = ref(false)

const disconnectedDescription = computed(() => {
  const lastHeartbeat = session.value?.last_heartbeat_at
  if (!lastHeartbeat) return 'The agent has not sent a heartbeat yet.'
  return `The last heartbeat arrived at ${new Date(lastHeartbeat).toLocaleString()}.`
})

function issueViewToken() {
  return api.liveSessions.issueViewToken(organizationId.value, orbitId.value, sessionId.value)
}

async function launch() {
  try {
    const { launch_url: launchUrl } = await issueViewToken()
    relayOrigin.value = new URL(launchUrl).origin
    frameUrl.value = launchUrl
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to open the live session')))
  }
}

async function openInNewTab() {
  // Opened before the token request, while the click still allows a new tab.
  const tab = window.open('', '_blank')
  if (!tab) {
    toast.add(simpleErrorToast('The browser blocked the new tab'))
    return
  }
  tab.opener = null
  try {
    const { launch_url: launchUrl } = await issueViewToken()
    tab.location.href = launchUrl
  } catch (e: unknown) {
    tab.close()
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to open the live session')))
  }
}

async function stopSession() {
  try {
    stopping.value = true
    session.value = await api.liveSessions.end(organizationId.value, orbitId.value, sessionId.value)
    frameUrl.value = null
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to stop the live session')))
  } finally {
    stopping.value = false
  }
}

async function loadSession() {
  try {
    session.value = await api.liveSessions.getItem(
      organizationId.value,
      orbitId.value,
      sessionId.value,
    )
  } catch (e: unknown) {
    if (isLiveSessionsNotConfigured(e)) {
      notConfigured.value = true
      return
    }
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load the live session')))
  }
}

/**
 * The relay's cookie ended, so the frame shows its page for missing access: launch
 * again with a new token. A second report inside the guard interval means the browser
 * does not keep the cookie in the frame, so launching again would loop forever.
 */
const AUTO_RELAUNCH_GUARD_MS = 30_000
let lastLaunchAt = 0

function onMessage(event: MessageEvent) {
  if (!relayOrigin.value || event.origin !== relayOrigin.value) return
  if (event.data?.type !== LIVE_SESSION_ACCESS_NEEDED_MESSAGE) return
  if (event.data.session !== sessionId.value) return
  const now = Date.now()
  if (now - lastLaunchAt > AUTO_RELAUNCH_GUARD_MS) {
    lastLaunchAt = now
    launch()
  } else {
    frameUrl.value = null
    frameBlocked.value = true
  }
}

onMounted(async () => {
  window.addEventListener('message', onMessage)
  await loadSession()
  loading.value = false
  if (session.value?.status === LiveSessionStatusEnum.live) {
    lastLaunchAt = Date.now()
    await launch()
  }
})

onUnmounted(() => {
  window.removeEventListener('message', onMessage)
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.page-header__icon {
  flex-shrink: 0;
  color: var(--p-primary-color);
}

.page-header__back {
  color: var(--p-text-muted-color);
  text-decoration: none;
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page-header__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.session-frame {
  width: 100%;
  height: calc(100vh - 160px);
  border: none;
  border-radius: 8px;
  background-color: var(--p-card-background);
}
</style>
