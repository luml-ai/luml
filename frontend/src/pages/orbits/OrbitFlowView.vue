<template>
  <div class="page-header">
    <div class="page-header__left">
      <ChartSpline :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Flow</h1>
    </div>
  </div>

  <div v-if="loading" class="loading-container">
    <Skeleton v-for="i in 3" :key="i" style="height: 56px" />
  </div>

  <div v-else-if="liveSessionsStore.notConfigured" class="notice" data-testid="not-configured">
    <TriangleAlert :size="20" class="notice__icon" />
    <p>Live sessions are not set up in this deployment.</p>
  </div>

  <div v-else-if="!liveSessionsStore.sessionsList.length" class="instructions">
    <FlowCommandCard
      title="Run Flow locally"
      :hints="RUN_LOCALLY_HINTS"
      :commands="RUN_LOCALLY_COMMANDS"
    />
    <FlowCommandCard
      title="Expose a running service"
      :hints="EXPOSE_HINTS"
      :commands="exposeCommands(organizationId, orbitId)"
    />
  </div>

  <ul v-else class="sessions">
    <li v-for="session in liveSessionsStore.sessionsList" :key="session.id">
      <router-link
        :to="{
          name: 'orbit-flow-session',
          params: { organizationId, id: orbitId, sessionId: session.id },
        }"
        class="session"
      >
        <span class="session__name">{{ session.name }}</span>
        <span class="session__started">{{ formatStartTime(session.started_at) }}</span>
        <span class="status" :class="`status--${session.status}`">{{ session.status }}</span>
      </router-link>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Skeleton, useToast } from 'primevue'
import { ChartSpline, TriangleAlert } from 'lucide-vue-next'
import { useLiveSessionsStore } from '@/stores/live-sessions'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import FlowCommandCard from '@/components/flow/FlowCommandCard.vue'
import {
  EXPOSE_HINTS,
  RUN_LOCALLY_COMMANDS,
  RUN_LOCALLY_HINTS,
  exposeCommands,
} from '@/components/flow/flow-commands'

const route = useRoute()
const toast = useToast()
const liveSessionsStore = useLiveSessionsStore()

const loading = ref(false)
const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

function formatStartTime(startedAt: string) {
  return new Date(startedAt).toLocaleString()
}

async function loadSessions() {
  try {
    loading.value = true
    await liveSessionsStore.loadSessions(organizationId.value, orbitId.value)
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load live sessions')))
  } finally {
    loading.value = false
  }
}

watch(
  orbitId,
  async (newId) => {
    if (!newId) return
    await loadSessions()
  },
  { immediate: true },
)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-header__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: var(--p-primary-color);
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notice {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  color: var(--p-text-muted-color);
}

.notice__icon {
  flex-shrink: 0;
  color: var(--p-orange-500);
}

.instructions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 48px;
  justify-items: center;
  padding: 32px 16px;
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.session {
  display: grid;
  grid-template-columns: 1fr auto 120px;
  align-items: center;
  gap: 24px;
  padding: 16px 24px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  color: var(--p-text-color);
  text-decoration: none;
}

.session:hover {
  background-color: var(--p-content-hover-background);
}

.session__name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session__started {
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.status {
  justify-self: end;
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.status--live {
  color: var(--p-green-500);
}

.status--disconnected {
  color: var(--p-orange-500);
}

@media (max-width: 992px) {
  .instructions {
    grid-template-columns: 1fr;
  }
}
</style>
