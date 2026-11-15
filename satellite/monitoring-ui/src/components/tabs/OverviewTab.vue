<template>
  <div>
    <OverviewLoader v-if="loading" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else class="overview">
      <OverviewCards :cards="cards" />
      <MAlerts v-if="data?.alert_banners?.length" :alerts="data.alert_banners" />
      <OverviewCharts v-if="data?.series?.length" :series="data.series" />
      <OverviewTopFeatures
        v-if="data?.top_drifted_features?.length"
        :features="data.top_drifted_features"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useHeaderStore } from '@/store/header'
import { isCardVisibleForKind } from '@/utils/cards'
import MErrorState from '@/components/MErrorState.vue'
import OverviewLoader from '@/components/overview/OverviewLoader.vue'
import OverviewCards from '@/components/overview/OverviewCards.vue'
import MAlerts from '@/components/MAlerts.vue'
import OverviewCharts from '@/components/overview/OverviewCharts.vue'
import OverviewTopFeatures from '@/components/overview/OverviewTopFeatures.vue'

const headerStore = useHeaderStore()

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getOverview(dims),
)

const cards = computed(() => {
  const isTabular = headerStore.modelKind === 'tabular'
  return (data.value?.cards ?? []).filter((card) => isCardVisibleForKind(card, isTabular))
})

watch(
  data,
  () => {
    console.log(data.value)
  },
  { immediate: true },
)
</script>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
