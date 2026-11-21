<template>
  <div>
    <OverviewLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="overview">
      <OverviewCards v-if="!emptyState" :cards="cards" />
      <MAlerts
        v-if="data.alert_banners?.length"
        :alerts="data.alert_banners"
        @select="alertDialog?.open($event)"
      />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <MStepSelector />
        <MSeriesCharts v-if="data.series?.length" :series="data.series" />
        <OverviewTopFeatures v-if="isTabular" :features="data.top_drifted_features ?? []" />
      </template>
    </div>
    <AlertDialogHost
      ref="alertDialog"
      :alerts="data?.alert_banners ?? []"
      :reload="reload"
      :error="error"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useHeaderStore } from '@/store/header'
import { isCardVisibleForKind } from '@/utils/cards'
import { getOverviewEmptyState } from '@/utils/overview'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import OverviewLoader from '@/components/overview/OverviewLoader.vue'
import OverviewCards from '@/components/overview/OverviewCards.vue'
import MAlerts from '@/components/MAlerts.vue'
import AlertDialogHost from '@/components/alerts/AlertDialogHost.vue'
import MSeriesCharts from '@/components/MSeriesCharts.vue'
import MStepSelector from '@/components/MStepSelector.vue'
import OverviewTopFeatures from '@/components/overview/OverviewTopFeatures.vue'

const headerStore = useHeaderStore()

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getOverview(dims),
)

const emptyState = computed(() => (data.value ? getOverviewEmptyState(data.value) : null))

const isTabular = computed(() => headerStore.modelKind === 'tabular')

const cards = computed(() =>
  (data.value?.cards ?? []).filter((card) => isCardVisibleForKind(card, isTabular.value)),
)

const alertDialog = useTemplateRef('alertDialog')
</script>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
