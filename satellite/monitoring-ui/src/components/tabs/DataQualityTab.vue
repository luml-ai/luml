<template>
  <div>
    <DataQualityLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="data-quality">
      <MStaleNotice v-if="data.stale" :computed-at="data.computed_at" />
      <MAlerts
        v-if="data.alerts?.length"
        :alerts="data.alerts"
        @select="alertDialog?.open($event)"
      />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <DataQualityTable v-else :features="data.features" @inspect="inspect" />
    </div>
    <DataQualityFeatureDialog v-model:visible="isInspecting" :row="inspectedRow" />
    <AlertDialogHost
      ref="alertDialog"
      :alerts="data?.alerts ?? []"
      :reload="reload"
      :error="error"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, shallowRef, useTemplateRef } from 'vue'
import type { DataQualityFeatureRow } from '@/api/monitoring/interfaces'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { useDataQualityStore } from '@/store/data-quality'
import { getDataQualityEmptyState } from '@/utils/data-quality'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MStaleNotice from '@/components/MStaleNotice.vue'
import MAlerts from '@/components/MAlerts.vue'
import AlertDialogHost from '@/components/alerts/AlertDialogHost.vue'
import DataQualityLoader from '@/components/data-quality/DataQualityLoader.vue'
import DataQualityTable from '@/components/data-quality/DataQualityTable.vue'
import DataQualityFeatureDialog from '@/components/data-quality/DataQualityFeatureDialog.vue'

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getDataQuality({ ...dims, feature: null }),
)

const dataQualityStore = useDataQualityStore()

const lastInspectedRow = shallowRef<DataQualityFeatureRow | null>(null)

const isInspecting = computed({
  get: () => inspectedRow.value !== null,
  set: (value: boolean) => {
    if (value) return
    dataQualityStore.inspect(null)
    lastInspectedRow.value = null
  },
})

const inspectedRow = computed(() => {
  const feature = dataQualityStore.inspectedFeature
  if (!feature) return null
  const row = data.value?.features.find((item) => item.feature === feature)
  if (row) return row
  return lastInspectedRow.value?.feature === feature ? lastInspectedRow.value : null
})

function inspect(row: DataQualityFeatureRow) {
  lastInspectedRow.value = row
  dataQualityStore.inspect(row.feature)
}

const emptyState = computed(() => (data.value ? getDataQualityEmptyState(data.value) : null))

const alertDialog = useTemplateRef('alertDialog')
</script>

<style scoped>
.data-quality {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
