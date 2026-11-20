<template>
  <Dialog
    v-model:visible="visible"
    modal
    block-scroll
    dismissable-mask
    :draggable="false"
    :style="dialogStyle"
    :pt="dialogPt"
  >
    <template #header>
      <AlertDialogHeader
        v-if="row"
        group="Data quality"
        :title="row.feature"
        :severity="row.status"
      />
    </template>
    <div v-if="row" class="content">
      <div class="cards">
        <AlertStatsCard title="Checks in this window" :rows="checkRows" />
        <template v-if="row.invalid">
          <AlertStatsCard
            v-if="row.invalid.unseen_category_count"
            title="Unseen categories"
            :rows="unseenRows"
            :note="getUnseenCategoriesNote(row.invalid)"
          />
          <AlertStatsCard
            v-if="row.invalid.range_violation_count"
            title="Out of range"
            :rows="getRangeViolationRows(row.invalid)"
          />
          <AlertStatsCard
            v-if="row.invalid.type_mismatch_count"
            title="Type errors"
            :rows="getTypeErrorRows(row.invalid)"
            :note="typeExamplesNote"
          />
        </template>
        <p v-else class="note">{{ noEvidenceNote }}</p>
      </div>
      <MErrorState v-if="error" :error="error" title="Failed to load history" @retry="reload" />
      <div v-else-if="loading && !trends" class="note">Loading history…</div>
      <MSeriesCharts v-else-if="trends?.length" :series="trends" />
      <p v-else class="note">
        One window is a reading, not a trend — the chart appears once the worker has materialized a
        second window.
      </p>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Dialog } from 'primevue'
import { api } from '@/api'
import type { DataQualityFeatureRow } from '@/api/monitoring/interfaces'
import { ALERT_DIALOG_GAP } from '@/constants/alerts'
import { useMonitoringData } from '@/composables/useMonitoringData'
import {
  getDataQualityCheckRows,
  getRangeViolationRows,
  getTypeErrorRows,
  getUnseenCategoriesNote,
  getUnseenCategoryRows,
  hasInvalidValues,
} from '@/utils/data-quality'
import AlertDialogHeader from '@/components/alerts/AlertDialogHeader.vue'
import AlertStatsCard from '@/components/alerts/AlertStatsCard.vue'
import MErrorState from '@/components/MErrorState.vue'
import MSeriesCharts from '@/components/MSeriesCharts.vue'

interface Props {
  row: DataQualityFeatureRow | null
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible', { required: true })

const dialogStyle = {
  width: `calc(100vw - ${2 * ALERT_DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * ALERT_DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}

const dialogPt = {
  mask: { style: { '--px-mask-background': 'transparent' } },
  header: { class: 'alert-dialog-header' },
  content: { class: 'alert-dialog-content' },
}

const inspectedFeature = computed(() => (visible.value ? (props.row?.feature ?? null) : null))

const {
  data: trends,
  loading,
  error,
  reload,
} = useMonitoringData(
  async (dims) => {
    const feature = inspectedFeature.value
    if (!feature) return null
    const response = await api.monitoring.getDataQuality({ ...dims, feature })
    return response.trends ?? []
  },
  () => inspectedFeature.value,
)

const checkRows = computed(() => (props.row ? getDataQualityCheckRows(props.row) : []))

const unseenRows = computed(() =>
  props.row?.invalid ? getUnseenCategoryRows(props.row.invalid) : [],
)

const typeExamplesNote = computed(() => {
  const examples = props.row?.invalid?.type_examples ?? []
  return examples.length ? `e.g. ${examples.join(', ')}` : undefined
})

const noEvidenceNote = computed(() =>
  props.row && hasInvalidValues(props.row)
    ? 'This window was computed before the per-value breakdown was recorded.'
    : 'Every value in this window matched the model contract.',
)
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 16px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.note {
  font-size: 14px;
  color: var(--p-text-muted-color);
}
</style>
