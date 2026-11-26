<template>
  <div>
    <FeatureDriftLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="feature-drift">
      <MStaleNotice v-if="data.stale" :computed-at="data.computed_at" />
      <MAlerts
        v-if="data.alerts?.length"
        :alerts="data.alerts"
        @select="alertDialog?.open($event)"
      />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <MEmpty
          v-if="!data.features.length"
          :title="NO_RANKED_FEATURES_STATE.title"
          :detail="NO_RANKED_FEATURES_STATE.detail"
        />
        <FeatureDriftPanel
          v-else
          :features="data.features"
          :selected="data.selected"
          :selected-feature="selectedFeature"
          :loading="loading"
          @select="filtersStore.setFeature"
        />
        <MEmpty
          v-if="multivariateEmptyState"
          :title="multivariateEmptyState.title"
          :detail="multivariateEmptyState.detail"
        />
        <MultivariateDrift v-else :multivariate="data.multivariate" />
      </template>
    </div>
    <AlertDialogHost
      ref="alertDialog"
      :alerts="data?.alerts ?? []"
      :reload="reload"
      :error="error"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, useTemplateRef, watch } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useFiltersStore } from '@/store/filters'
import {
  NO_RANKED_FEATURES_STATE,
  getFeatureDriftEmptyState,
  getMultivariateEmptyState,
} from '@/utils/drift'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MStaleNotice from '@/components/MStaleNotice.vue'
import MAlerts from '@/components/MAlerts.vue'
import AlertDialogHost from '@/components/alerts/AlertDialogHost.vue'
import FeatureDriftLoader from '@/components/feature-drift/FeatureDriftLoader.vue'
import FeatureDriftPanel from '@/components/feature-drift/FeatureDriftPanel.vue'
import MultivariateDrift from '@/components/feature-drift/MultivariateDrift.vue'

const filtersStore = useFiltersStore()

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getFeatureDrift(dims),
)

const selectedFeature = computed(() => {
  const loadedFeature = data.value?.selected?.feature ?? null
  return loading.value ? (filtersStore.feature ?? loadedFeature) : loadedFeature
})

watch(data, (value) => {
  const topFeature = value?.features[0]?.feature
  if (!filtersStore.feature && topFeature) filtersStore.setFeature(topFeature)
})

const emptyState = computed(() => (data.value ? getFeatureDriftEmptyState(data.value) : null))

const multivariateEmptyState = computed(() =>
  data.value ? getMultivariateEmptyState(data.value.multivariate) : null,
)

const alertDialog = useTemplateRef('alertDialog')
</script>

<style scoped>
.feature-drift {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
