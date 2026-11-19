<template>
  <Dialog
    v-model:visible="visible"
    modal
    block-scroll
    dismissable-mask
    :draggable="false"
    :style="dialogStyle"
    :pt="dialogPt"
    @after-hide="emit('hidden')"
  >
    <template #header>
      <AlertDialogHeader
        v-if="alert"
        :group="getAlertGroupLabel(alert.group)"
        :title="getAlertName(alert)"
        :severity="alert.severity"
      />
    </template>
    <div v-if="alert" class="content">
      <div class="cards">
        <AlertStatsCard title="Reading" :rows="readingRows" :note="getAlertThresholdNote(alert)" />
        <AlertStatsCard title="Since when" :rows="timingRows" />
      </div>
      <MScalableCard class="chart" title="Metric over time" variant="block">
        <template #default>
          <MSeriesChart
            v-if="alert.history"
            :series="alert.history"
            :threshold="alert.threshold"
            :color="getAlertChartColor(alert.severity)"
            height="100%"
          />
          <p v-else class="chart-empty">
            The metric has been materialized once in this window — a second one turns this into a
            trend.
          </p>
        </template>
      </MScalableCard>
      <div class="actions">
        <Button
          v-if="targetTab"
          :label="showLabel"
          severity="secondary"
          variant="outlined"
          @click="emit('show', alert)"
        />
        <Button
          :label="acknowledged ? 'Acknowledged' : 'Acknowledge'"
          severity="secondary"
          :disabled="acknowledged"
          :loading="acknowledging"
          @click="emit('acknowledge', alert)"
        />
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button, Dialog } from 'primevue'
import type { AlertBanner } from '@/api/monitoring/interfaces'
import { useTabsStore } from '@/store/tabs'
import { ALERT_DIALOG_GAP } from '@/constants/alerts'
import {
  formatDuration,
  getAlertChartColor,
  getAlertGroupLabel,
  getAlertName,
  getAlertState,
  getAlertTargetTab,
  getAlertThreshold,
  getAlertThresholdNote,
  getAlertValue,
  getAlertValueColor,
  isAlertAcknowledged,
} from '@/utils/alerts'
import { formatTimestamp } from '@/utils/format'
import type { AlertStatsRow } from '@/types/alerts'
import MScalableCard from '@/components/MScalableCard.vue'
import MSeriesChart from '@/components/MSeriesChart.vue'
import AlertDialogHeader from '@/components/alerts/AlertDialogHeader.vue'
import AlertStatsCard from '@/components/alerts/AlertStatsCard.vue'

interface Props {
  alert: AlertBanner | null
  acknowledging?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  acknowledging: false,
})

const emit = defineEmits<{
  acknowledge: [alert: AlertBanner]
  show: [alert: AlertBanner]
  hidden: []
}>()

const visible = defineModel<boolean>('visible', { required: true })

const tabsStore = useTabsStore()

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

const acknowledged = computed(() => (props.alert ? isAlertAcknowledged(props.alert) : false))

const targetTab = computed(() => {
  const tab = props.alert ? getAlertTargetTab(props.alert) : null
  return tab && tabsStore.tabs.some(({ key }) => key === tab) ? tab : null
})

const showLabel = computed(() => {
  if (!props.alert) return ''
  const subject = props.alert.feature ?? props.alert.label ?? props.alert.metric
  return `Show ${subject} in ${getAlertGroupLabel(props.alert.group)}`
})

const readingRows = computed<AlertStatsRow[]>(() => {
  const alert = props.alert
  if (!alert) return []
  return [
    {
      label: alert.label ?? 'Current value',
      value: getAlertValue(alert),
      color: getAlertValueColor(alert.severity),
    },
    { label: 'Threshold', value: getAlertThreshold(alert) },
    { label: 'State', value: getAlertState(alert) },
  ]
})

const timingRows = computed<AlertStatsRow[]>(() => {
  const alert = props.alert
  if (!alert) return []
  return [
    { label: 'Firing for', value: formatDuration(alert.duration_seconds) },
    { label: 'First seen', value: formatTimestamp(alert.first_seen) },
    { label: 'Last confirmed', value: formatTimestamp(alert.last_seen) },
  ]
})
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
}

.chart {
  flex: 1;
  min-height: 240px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 120px;
  font-size: 14px;
  color: var(--p-text-muted-color);
  text-align: center;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 16px;
}
</style>

<style>
.alert-dialog-header {
  border-bottom: 1px solid var(--p-content-border-color);
}

.alert-dialog-content {
  flex: 1;
  min-height: 0;
  padding-top: 16px;
}
</style>
