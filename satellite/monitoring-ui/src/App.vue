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

    <DataQualityTab
      v-else-if="activeTab === 'data-quality'"
      :data-quality="dataQuality"
      :status="dataQualityStatus"
      :traces="traces"
      :traces-status="tracesStatus"
      :open-trace-id="openTraceId"
      :trace-detail="traceDetail"
      :trace-detail-status="traceDetailStatus"
      @traces-page="setTracesPage"
      @trace-open="openTrace"
      @trace-close="closeTrace"
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
import DataQualityTab from '@/components/data-quality/DataQualityTab.vue'
import FeatureDriftTab from '@/components/feature-drift/FeatureDriftTab.vue'

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
