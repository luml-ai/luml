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

    <OverviewTab
      v-if="activeTab === 'overview'"
      :overview="overview"
      :status="overviewStatus"
      :worker-health="workerHealth"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />

    <TracesTab
      v-else-if="activeTab === 'traces'"
      :traces="traces"
      :status="tracesStatus"
      :open-trace-id="openTraceId"
      :trace-detail="traceDetail"
      :trace-detail-status="traceDetailStatus"
      @page="setTracesPage"
      @open="openTrace"
      @close-trace="closeTrace"
    />

    <DataQualityTab
      v-else-if="activeTab === 'data-quality'"
      :data-quality="dataQuality"
      :status="dataQualityStatus"
      :trends="qualityTrends"
      :trends-status="qualityTrendsStatus"
      :focus-feature="focusedFeature"
      @inspect="loadQualityTrends"
    />

    <AlertsTab
      v-else-if="activeTab === 'alerts'"
      :alerts="alerts"
      :status="alertsStatus"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />

    <ReferenceProfileTab
      v-else-if="activeTab === 'reference-profile'"
      :profile="profileDocument"
      :status="profileDocumentStatus"
    />

    <FeatureDriftTab
      v-else
      :feature-drift="featureDrift"
      :status="featureDriftStatus"
      :selected-feature="dimensions.feature"
      :reference-profile="referenceProfile"
      :reference-profile-status="referenceProfileStatus"
      @select-feature="setFeature"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useMonitoringDashboard } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import DashboardHeader from '@/components/DashboardHeader.vue'
import GlobalControls from '@/components/GlobalControls.vue'
import DashboardTabs from '@/components/DashboardTabs.vue'
import PlaceholderBanner from '@/components/PlaceholderBanner.vue'
import SessionExpiredOverlay from '@/components/SessionExpiredOverlay.vue'
import StateBlock from '@/components/StateBlock.vue'
import OverviewTab from '@/components/overview/OverviewTab.vue'
import TracesTab from '@/components/traces/TracesTab.vue'
import DataQualityTab from '@/components/data-quality/DataQualityTab.vue'
import FeatureDriftTab from '@/components/feature-drift/FeatureDriftTab.vue'
import ReferenceProfileTab from '@/components/reference-profile/ReferenceProfileTab.vue'
import AlertsTab from '@/components/alerts/AlertsTab.vue'

const {
  dimensions,
  activeTab,
  sessionExpired,
  header,
  headerStatus,
  overview,
  overviewStatus,
  dataQuality,
  dataQualityStatus,
  qualityTrends,
  qualityTrendsStatus,
  loadQualityTrends,
  profileDocument,
  profileDocumentStatus,
  alerts,
  alertsStatus,
  acknowledgeAlert,
  workerHealth,
  focusAlert,
  focusedFeature,
  traces,
  tracesStatus,
  openTraceId,
  traceDetail,
  traceDetailStatus,
  openTrace,
  closeTrace,
  featureDrift,
  featureDriftStatus,
  referenceProfile,
  referenceProfileStatus,
  isPlaceholderProfile,
  load,
  refresh,
  setWindow,
  setCompare,
  setSeverity,
  setFeature,
  setTracesPage,
  setActiveTab,
} = useMonitoringDashboard()

const headerView = computed(() => sectionView(headerStatus.value, header.value?.state))

onMounted(() => {
  void load()
})
</script>
