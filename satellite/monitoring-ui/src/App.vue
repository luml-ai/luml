<template>
  <main class="app" data-testid="monitoring-app">
    <MEmpty
      v-if="isSessionExpired"
      class="session-expired"
      title="Session expired"
      detail="Your monitoring session has ended. Reopen monitoring from the Platform to continue."
      data-testid="session-expired"
    />
    <template v-else>
      <div v-if="headerStore.title" class="title-row">
        <h2 class="title">{{ headerStore.title }}</h2>
        <Tag
          v-if="headerStore.status"
          :value="getDeploymentStatusLabel(headerStore.status)"
          :severity="getDeploymentStatusSeverity(headerStore.status)"
          data-testid="deployment-status"
        />
      </div>
      <MErrorState
        v-if="headerStore.isContextMissing && headerStore.error"
        class="header-notice"
        title="Deployment details are unavailable, so model-specific tabs are hidden"
        :error="headerStore.error"
        @retry="headerStore.loadHeader"
      />
      <Message
        v-else-if="headerStore.isContextMissing"
        severity="warn"
        class="header-notice"
        data-testid="header-unavailable"
      >
        <template #icon>
          <TriangleAlert :size="16" />
        </template>
        <div class="notice-text">
          <span class="notice-title">Deployment details are unavailable</span>
          <span class="notice-detail">
            The model type is unknown, so data quality, drift and reference profile tabs are hidden
            until it loads.
          </span>
        </div>
      </Message>
      <MWorkerStatus :health="headerStore.workerHealth" />
      <Message
        v-if="headerStore.isPlaceholderProfile"
        severity="warn"
        class="header-notice"
        role="status"
        data-testid="placeholder-banner"
      >
        <template #icon>
          <Info :size="16" />
        </template>
        <div class="notice-text">
          <span class="notice-title">Reference profile is a placeholder</span>
          <span class="notice-detail">
            A real training baseline has not been loaded, so drift and distribution views are
            approximate until it is generated.
          </span>
        </div>
      </Message>
      <MTabs />
      <MFilters />
      <MTabsContent v-if="settingsStore.isReady" />
    </template>
    <Toast />
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Message, Tag, Toast } from 'primevue'
import { Info, TriangleAlert } from 'lucide-vue-next'
import { isSessionExpired } from './api'
import MEmpty from './components/MEmpty.vue'
import MErrorState from './components/MErrorState.vue'
import MFilters from './components/filters/MFilters.vue'
import MTabs from './components/MTabs.vue'
import MTabsContent from './components/MTabsContent.vue'
import MWorkerStatus from './components/MWorkerStatus.vue'
import { useHeaderStore } from './store/header'
import { useSettingsStore } from './store/settings'
import { getDeploymentStatusLabel, getDeploymentStatusSeverity } from './utils/deployment'

const headerStore = useHeaderStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  void headerStore.loadHeader()
  void settingsStore.restore()
})
</script>

<style scoped>
.app {
  min-height: 100vh;
  padding: 16px;
}

.title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.title {
  font-size: 24px;
  font-weight: 500;
}

.header-notice {
  margin-bottom: 20px;
}

.notice-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.notice-title {
  font-size: 14px;
  font-weight: 500;
}

.notice-detail {
  font-size: 12px;
}

.session-expired {
  max-width: 480px;
  margin: 80px auto 0;
}
</style>
