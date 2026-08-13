<template>
  <nav class="tabs" data-testid="dashboard-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      class="tab"
      :class="{ active: tab.key === active }"
      :data-testid="`tab-${tab.key}`"
      @click="$emit('select', tab.key)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>

<script setup lang="ts">
import { DASHBOARD_TABS, type TabKey } from '@/composables/useMonitoringDashboard'

defineProps<{ active: TabKey }>()
defineEmits<{ select: [TabKey] }>()

const tabs = DASHBOARD_TABS
</script>

<style scoped>
.tabs {
  display: flex;
  gap: var(--luml-space-6);
  border-bottom: 1px solid var(--luml-border);
}
.tab {
  border: none;
  background: transparent;
  padding: var(--luml-space-3) 2px;
  margin-bottom: -1px;
  font: inherit;
  font-size: var(--luml-text-base);
  font-weight: 500;
  color: var(--luml-fg-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.tab:hover {
  color: var(--luml-fg-strong);
}
.tab.active {
  color: var(--luml-brand);
  border-bottom-color: var(--luml-brand);
}
</style>
