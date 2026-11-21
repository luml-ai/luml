<template>
  <div>
    <OutputDriftLoader v-if="loading && !data" />
    <MErrorState v-else-if="error" :error="error" @retry="reload" />
    <div v-else-if="data" class="output-drift">
      <MStaleNotice v-if="data.stale" :computed-at="data.computed_at" />
      <MAlerts
        v-if="data.alerts?.length"
        :alerts="data.alerts"
        @select="alertDialog?.open($event)"
      />
      <MEmpty v-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else>
        <OutputDriftPsiCard :data="data" />
        <OutputDriftCharts :data="data" />
        <OutputDriftClassList
          v-if="horizonRows.length"
          title="Drift by horizon"
          subtitle="each forecast horizon vs its training baseline"
          :rows="horizonRows"
        />
        <OutputDriftConfidence v-if="data.confidence" :confidence="data.confidence" />
        <MCard
          v-if="nearThreshold"
          label="NEAR DECISION THRESHOLD"
          :content="formatPercent(nearThreshold.rate)"
        >
          <template #footer>
            <span class="footer">{{ formatNearThresholdDetail(nearThreshold) }}</span>
          </template>
        </MCard>
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
    <AlertDialogHost
      ref="alertDialog"
      :alerts="data?.alerts ?? []"
      :reload="reload"
      :error="error"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { api } from '@/api'
import { useMonitoringData } from '@/composables/useMonitoringData'
import { formatPercent } from '@/utils/format'
import {
  formatNearThresholdDetail,
  getHorizonRows,
  getOutputDriftEmptyState,
  getProbabilityRows,
  getTopChangedRows,
} from '@/utils/output-drift'
import MErrorState from '@/components/MErrorState.vue'
import MEmpty from '@/components/MEmpty.vue'
import MStaleNotice from '@/components/MStaleNotice.vue'
import MAlerts from '@/components/MAlerts.vue'
import MCard from '@/components/MCard.vue'
import AlertDialogHost from '@/components/alerts/AlertDialogHost.vue'
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

const nearThreshold = computed(() => data.value?.probabilities?.near_threshold ?? null)

const horizonRows = computed(() => getHorizonRows(data.value?.horizons ?? []))

const topChangedRows = computed(() => getTopChangedRows(data.value?.top_changed ?? []))

const alertDialog = useTemplateRef('alertDialog')
</script>

<style scoped>
.output-drift {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.footer {
  color: var(--p-text-muted-color);
}
</style>
