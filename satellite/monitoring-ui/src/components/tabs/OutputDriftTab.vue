<template>
  <div>
    <OutputDriftLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="output-drift">
      <MAlerts v-if="data.alerts?.length" :alerts="data.alerts" />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <OutputDriftPsiCard :data="data" />
        <OutputDriftCharts :data="data" />
        <OutputDriftConfidence v-if="data.confidence" :confidence="data.confidence" />
        <OutputDriftClassList
          v-if="probabilityRows.length"
          title="Probability drift by class"
          subtitle="each class's probability distribution vs its training baseline"
          :rows="probabilityRows"
        />
        <OutputDriftClassList
          v-if="topChangedRows.length"
          title="Top changed classes"
          subtitle="share of predictions vs the training reference"
          :rows="topChangedRows"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import {
  getOutputDriftEmptyState,
  getProbabilityRows,
  getTopChangedRows,
} from '@/utils/output-drift'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MAlerts from '@/components/MAlerts.vue'
import OutputDriftLoader from '@/components/output-drift/OutputDriftLoader.vue'
import OutputDriftPsiCard from '@/components/output-drift/OutputDriftPsiCard.vue'
import OutputDriftCharts from '@/components/output-drift/OutputDriftCharts.vue'
import OutputDriftConfidence from '@/components/output-drift/OutputDriftConfidence.vue'
import OutputDriftClassList from '@/components/output-drift/OutputDriftClassList.vue'

const { data, loading, error, reload } = useMonitoringData((dims) =>
  api.monitoring.getOutputDrift(dims),
)

const emptyState = computed(() => (data.value ? getOutputDriftEmptyState(data.value) : null))

const probabilityRows = computed(() =>
  getProbabilityRows(data.value?.probabilities?.per_class ?? []),
)

const topChangedRows = computed(() => getTopChangedRows(data.value?.top_changed ?? []))
</script>

<style scoped>
.output-drift {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
