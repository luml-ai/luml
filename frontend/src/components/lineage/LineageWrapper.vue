<template>
  <div class="wrapper">
    <LineageHeading v-if="isMaximized" title="Lineage" class="heading"></LineageHeading>
    <LineageToolbar class="toolbar"></LineageToolbar>
    <LineageStateControls class="state-controls"></LineageStateControls>
    <LineageActions v-model:is-maximized="isMaximized" class="actions"></LineageActions>
    <div v-if="lineageStore.isLoading" class="notice notice--loading">
      <ProgressSpinner class="spinner" />
    </div>
    <div v-else-if="lineageStore.loadFailed" class="notice">
      Lineage could not be loaded — refresh the page to try again
    </div>
    <div v-else-if="!lineageStore.hasEdges" class="notice">
      No lineage recorded yet — link an artifact to get started
    </div>
    <div v-if="!lineageStore.isLoading && lineageStore.truncated" class="limit-notice">
      Graph is limited to 200 artifacts — the most distant connections are hidden, so artifacts
      cannot be unlinked or replaced here
    </div>
    <LineageArea></LineageArea>
  </div>
</template>

<script setup lang="ts">
import LineageStateControls from './LineageStateControls.vue'
import LineageToolbar from './LineageToolbar.vue'
import LineageArea from './LineageArea.vue'
import LineageActions from './LineageActions.vue'
import LineageHeading from './LineageHeading.vue'
import { useLineageStore } from '@/stores/lineage'
import { ProgressSpinner } from 'primevue'

const isMaximized = defineModel('isMaximized', { default: false })
const lineageStore = useLineageStore()
</script>

<style scoped>
.wrapper {
  height: 100%;
  position: relative;
}

.toolbar {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
}

.state-controls {
  position: absolute;
  left: 20px;
  bottom: 28px;
  z-index: 10;
}

.actions {
  position: absolute;
  right: 20px;
  top: 28px;
  z-index: 10;
}

.heading {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 10;
}

.notice {
  position: absolute;
  left: 50%;
  top: 24px;
  z-index: 5;
  transform: translateX(-50%);
  padding: 8px 12px;
  border-radius: 8px;
  color: var(--p-text-muted-color);
  background: color-mix(in srgb, var(--p-card-background) 92%, transparent);
  box-shadow: var(--card-shadow);
  font-size: 13px;
  pointer-events: none;
}

.notice--loading {
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  width: 24px;
  height: 24px;
}

.limit-notice {
  position: absolute;
  left: 20px;
  top: 20px;
  z-index: 5;
  max-width: 360px;
  padding: 8px 12px;
  border: 1px solid var(--p-orange-300);
  border-radius: 8px;
  color: var(--p-orange-700);
  background: var(--p-orange-50);
  font-size: 13px;
}

.heading ~ .limit-notice {
  top: 64px;
}
</style>
