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
      :auto-refresh="autoRefreshSeconds"
      @update:window="setWindow"
      @update:range="setCustomRange"
      @update:severity="setSeverity"
      @update:auto="setAutoRefresh"
      @open-compare="compareOpen = true"
      @refresh="refresh"
    />

    <!-- Compare mode is page state, not a per-tab detail: the strip stays visible on
         every tab so nobody reads ghost lines and deltas as plain data. -->
    <div v-if="comparing" class="compare-strip" data-testid="compare-strip">
      <ArrowLeftRight :size="13" />
      <span>Comparing with {{ compareLabel }}</span>
      <button
        type="button"
        class="strip-off"
        aria-label="Turn comparison off"
        data-testid="compare-off"
        @click="setCompare(Compare.OFF)"
      >
        <X :size="13" />
      </button>
    </div>

    <CompareDrawer
      :open="compareOpen"
      :dimensions="dimensions"
      @close="compareOpen = false"
      @apply="applyCompare"
    />

    <div v-if="recordingOff" class="recording-status" role="alert" data-testid="recording-status">
      <strong>Recording is off.</strong> {{ workerHealth?.recording?.reason }}
    </div>

    <PlaceholderBanner v-if="isPlaceholderProfile" />

    <DashboardTabs :active="activeTab" :tabs="visibleTabs" @select="setActiveTab" />

    <!-- Refetches keep the previous content on screen, only dimmed: swapping a full
         tab for a skeleton on every reload made each click feel like a page load. -->
    <div class="tab-stage" :class="{ refreshing }">
    <OverviewTab
      v-if="activeTab === 'overview'"
      :overview="overview"
      :status="overviewStatus"
      :worker-health="workerHealth"
      :granularity="dimensions.granularity"
      :model-kind="header?.model_kind"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
      @update:granularity="setGranularity"
    />

    <RuntimeTab
      v-else-if="activeTab === 'runtime'"
      :runtime="runtime"
      :status="runtimeStatus"
      :granularity="dimensions.granularity"
      :compare="dimensions.compare"
      @acknowledge="acknowledgeAlert($event.metric)"
      @update:granularity="setGranularity"
    />

    <TracesTab
      v-else-if="activeTab === 'traces'"
      :traces="traces"
      :status="tracesStatus"
      :open-trace-id="openTraceId"
      :trace-detail="traceDetail"
      :trace-detail-status="traceDetailStatus"
      :new-count="tracesNewCount"
      :sort-key="tracesSort.key"
      :sort-order="tracesSort.order"
      @page="setTracesPage"
      @open="openTrace"
      @close-trace="closeTrace"
      @show-latest="showLatestTraces"
      @sort="setTracesSort"
    />

    <DataQualityTab
      v-else-if="activeTab === 'data-quality'"
      :data-quality="dataQuality"
      :status="dataQualityStatus"
      :window="dimensions.window"
      :trends="qualityTrends"
      :trends-status="qualityTrendsStatus"
      :focus-feature="focusedFeature"
      @inspect="loadQualityTrends"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />

    <AlertsTab
      v-else-if="activeTab === 'alerts'"
      :alerts="alerts"
      :status="alertsStatus"
      :new-count="alertsNewCount"
      :fresh-keys="alertsFreshKeys"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
      @seen="markAlertsSeen"
    />

    <OutputDriftTab
      v-else-if="activeTab === 'output-drift'"
      :output-drift="outputDrift"
      :status="outputDriftStatus"
      :window="dimensions.window"
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
      :window="dimensions.window"
      :selected-feature="dimensions.feature"
      :reference-profile="referenceProfile"
      :reference-profile-status="referenceProfileStatus"
      @select-feature="setFeature"
      @show-feature="focusAlert"
      @acknowledge="acknowledgeAlert($event.metric)"
    />
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowLeftRight, X } from 'lucide-vue-next'
import { Compare } from '@/api/types'
import { useMonitoringDashboard } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import DashboardHeader from '@/components/DashboardHeader.vue'
import GlobalControls from '@/components/GlobalControls.vue'
import CompareDrawer from '@/components/CompareDrawer.vue'
import DashboardTabs from '@/components/DashboardTabs.vue'
import PlaceholderBanner from '@/components/PlaceholderBanner.vue'
import SessionExpiredOverlay from '@/components/SessionExpiredOverlay.vue'
import StateBlock from '@/components/StateBlock.vue'
import OverviewTab from '@/components/overview/OverviewTab.vue'
import RuntimeTab from '@/components/runtime/RuntimeTab.vue'
import TracesTab from '@/components/traces/TracesTab.vue'
import DataQualityTab from '@/components/data-quality/DataQualityTab.vue'
import FeatureDriftTab from '@/components/feature-drift/FeatureDriftTab.vue'
import OutputDriftTab from '@/components/output-drift/OutputDriftTab.vue'
import ReferenceProfileTab from '@/components/reference-profile/ReferenceProfileTab.vue'
import AlertsTab from '@/components/alerts/AlertsTab.vue'

const {
  dimensions,
  activeTab,
  visibleTabs,
  sessionExpired,
  header,
  headerStatus,
  overview,
  overviewStatus,
  runtime,
  runtimeStatus,
  dataQuality,
  dataQualityStatus,
  qualityTrends,
  qualityTrendsStatus,
  loadQualityTrends,
  profileDocument,
  profileDocumentStatus,
  alerts,
  alertsStatus,
  alertsNewCount,
  alertsFreshKeys,
  markAlertsSeen,
  acknowledgeAlert,
  workerHealth,
  focusAlert,
  focusedFeature,
  traces,
  tracesStatus,
  tracesNewCount,
  showLatestTraces,
  tracesSort,
  setTracesSort,
  openTraceId,
  traceDetail,
  traceDetailStatus,
  openTrace,
  closeTrace,
  featureDrift,
  featureDriftStatus,
  outputDrift,
  outputDriftStatus,
  referenceProfile,
  referenceProfileStatus,
  isPlaceholderProfile,
  autoRefreshSeconds,
  setAutoRefresh,
  load,
  refresh,
  setWindow,
  setCustomRange,
  setComparePeriods,
  setGranularity,
  setCompare,
  setSeverity,
  setFeature,
  setTracesPage,
  setActiveTab,
} = useMonitoringDashboard()

const recordingOff = computed(() => {
  const state = workerHealth.value?.recording?.state
  return state !== undefined && state !== 'recording'
})

const headerView = computed(() => sectionView(headerStatus.value, header.value?.state))

const compareOpen = ref(false)

const comparing = computed(
  () => dimensions.compare === Compare.PREVIOUS || dimensions.compare === Compare.CUSTOM,
)

const compareLabel = computed(() => {
  if (dimensions.compare === Compare.PREVIOUS) return 'the previous period'
  const fmt = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleString(undefined, {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      : ''
  return `${fmt(dimensions.compareStart)} — ${fmt(dimensions.compareEnd)}`
})

function applyCompare(
  mode: Compare,
  periods: { start: string; end: string; compareStart: string; compareEnd: string } | null,
): void {
  compareOpen.value = false
  if (mode === Compare.CUSTOM && periods !== null) {
    void setComparePeriods(periods.start, periods.end, periods.compareStart, periods.compareEnd)
    return
  }
  void setCompare(mode)
}

/** The active tab is fetching; its stale content stays up, dimmed a touch. */
const refreshing = computed(() => {
  const status = {
    overview: overviewStatus,
    runtime: runtimeStatus,
    traces: tracesStatus,
    'data-quality': dataQualityStatus,
    'feature-drift': featureDriftStatus,
    'output-drift': outputDriftStatus,
    'reference-profile': profileDocumentStatus,
    alerts: alertsStatus,
  }[activeTab.value]
  return status?.value === 'loading'
})

onMounted(() => {
  void load()
})
</script>

<style scoped>
.recording-status {
  padding: 12px;
  border: 1px solid var(--luml-danger);
  border-radius: var(--luml-radius-md);
  color: var(--luml-danger-tint-fg);
  background: var(--luml-bg-card);
}
.compare-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 6px 12px;
  border: 1px solid var(--luml-brand-tint-strong);
  border-radius: var(--luml-radius-pill);
  background: var(--luml-brand-tint);
  color: var(--luml-brand);
  font-size: 12.5px;
  font-weight: 500;
}
.strip-off {
  display: inline-flex;
  align-items: center;
  border: none;
  background: transparent;
  color: inherit;
  padding: 0;
  cursor: pointer;
  opacity: 0.7;
}
.strip-off:hover {
  opacity: 1;
}
.tab-stage {
  transition: opacity 0.15s ease;
}
/* The delay keeps fast refetches invisible; only a slow one dims at all. */
.tab-stage.refreshing {
  opacity: 0.55;
  transition-delay: 0.2s;
  pointer-events: none;
}
</style>
