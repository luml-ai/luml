<template>
  <div>
    <FeatureDriftLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="feature-drift">
      <MAlerts v-if="data.alerts?.length" :alerts="data.alerts" />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <FeatureDriftPanel
          :features="data.features"
          :selected="data.selected"
          :selected-feature="selectedFeature"
          :loading="loading"
          @select="filtersStore.setFeature"
          @open-reference="tabsStore.setActiveTab(TabKey.REFERENCE_PROFILE)"
        />
        <MEmpty
          v-if="multivariateEmptyState"
          :title="multivariateEmptyState.title"
          :detail="multivariateEmptyState.detail"
        />
        <MultivariateDrift
          v-else
          :multivariate="data.multivariate"
          :total-features="data.features.length"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useFiltersStore } from '@/store/filters'
import { useTabsStore } from '@/store/tabs'
import { TabKey } from '@/types/tabs'
import { getFeatureDriftEmptyState, getMultivariateEmptyState } from '@/utils/drift'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MAlerts from '@/components/MAlerts.vue'
import FeatureDriftLoader from '@/components/feature-drift/FeatureDriftLoader.vue'
import FeatureDriftPanel from '@/components/feature-drift/FeatureDriftPanel.vue'
import MultivariateDrift from '@/components/feature-drift/MultivariateDrift.vue'

const filtersStore = useFiltersStore()
const tabsStore = useTabsStore()

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getFeatureDrift(dims),
)

const selectedFeature = computed(() => {
  const loadedFeature = data.value?.selected?.feature ?? null
  return loading.value ? (filtersStore.feature ?? loadedFeature) : loadedFeature
})

const emptyState = computed(() => (data.value ? getFeatureDriftEmptyState(data.value) : null))

const multivariateEmptyState = computed(() =>
  data.value ? getMultivariateEmptyState(data.value.multivariate) : null,
)
</script>

<style scoped>
.feature-drift {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
