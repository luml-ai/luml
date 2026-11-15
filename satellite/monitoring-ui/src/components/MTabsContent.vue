<template>
  <div class="tabs-content">
    <component :is="activeComponent" />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, type Component } from 'vue'
import { useTabsStore } from '@/store/tabs'
import { TabKey } from '@/types/tabs'

const TAB_COMPONENTS: Record<TabKey, Component> = {
  [TabKey.OVERVIEW]: defineAsyncComponent(() => import('./tabs/OverviewTab.vue')),
  [TabKey.RUNTIME]: defineAsyncComponent(() => import('./tabs/RuntimeTab.vue')),
  [TabKey.TRACES]: defineAsyncComponent(() => import('./tabs/TracesTab.vue')),
  [TabKey.DATA_QUALITY]: defineAsyncComponent(() => import('./tabs/DataQualityTab.vue')),
  [TabKey.FEATURE_DRIFT]: defineAsyncComponent(() => import('./tabs/FeatureDriftTab.vue')),
  [TabKey.OUTPUT_DRIFT]: defineAsyncComponent(() => import('./tabs/OutputDriftTab.vue')),
  [TabKey.REFERENCE_PROFILE]: defineAsyncComponent(() => import('./tabs/ReferenceProfileTab.vue')),
  [TabKey.ALERTS]: defineAsyncComponent(() => import('./tabs/AlertsTab.vue')),
}

const tabsStore = useTabsStore()

const activeComponent = computed(() => TAB_COMPONENTS[tabsStore.activeTab])
</script>

<style scoped>
.tabs-content {
  padding-top: 20px;
}
</style>
