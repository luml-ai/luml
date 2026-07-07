<template>
  <SessionExpiredOverlay v-if="sessionExpired" />

  <main v-else class="dashboard">
    <DashboardHeader v-if="header && headerView === 'ready'" :header="header" />
    <StateBlock
      v-else
      :view="headerView"
      :skeleton-rows="2"
      error-title="Deployment context unavailable"
    />

    <GlobalControls
      :dimensions="dimensions"
      @update:window="setWindow"
      @update:compare="setCompare"
      @update:severity="setSeverity"
      @refresh="refresh"
    />

    <PlaceholderBanner v-if="isPlaceholderProfile" />

    <DashboardTabs :active="activeTab" @select="setActiveTab" />

    <OverviewTab v-if="activeTab === 'overview'" :overview="overview" :status="overviewStatus" />
    <ComingSoonPanel v-else :title="activeTabLabel" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { DASHBOARD_TABS, useMonitoringDashboard } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import DashboardHeader from '@/components/DashboardHeader.vue'
import GlobalControls from '@/components/GlobalControls.vue'
import DashboardTabs from '@/components/DashboardTabs.vue'
import PlaceholderBanner from '@/components/PlaceholderBanner.vue'
import SessionExpiredOverlay from '@/components/SessionExpiredOverlay.vue'
import StateBlock from '@/components/StateBlock.vue'
import ComingSoonPanel from '@/components/ComingSoonPanel.vue'
import OverviewTab from '@/components/overview/OverviewTab.vue'

const {
  dimensions,
  activeTab,
  sessionExpired,
  header,
  headerStatus,
  overview,
  overviewStatus,
  isPlaceholderProfile,
  load,
  refresh,
  setWindow,
  setCompare,
  setSeverity,
  setActiveTab,
} = useMonitoringDashboard()

const headerView = computed(() => sectionView(headerStatus.value, header.value?.state))

const activeTabLabel = computed(
  () => DASHBOARD_TABS.find((tab) => tab.key === activeTab.value)?.label ?? '',
)

onMounted(() => {
  void load()
})
</script>
