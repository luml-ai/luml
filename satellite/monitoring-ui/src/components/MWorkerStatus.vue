<template>
  <div v-if="hasContent" class="worker-status">
    <Message v-if="recordingOff" severity="error" role="alert" data-testid="recording-status">
      <template #icon>
        <CircleAlert :size="16" />
      </template>
      <div class="status-text">
        <span class="status-title">Recording is off</span>
        <span class="status-detail">{{ recordingDetail }}</span>
      </div>
    </Message>
    <Message v-if="failureSummary" severity="warn" data-testid="worker-failures">
      <template #icon>
        <TriangleAlert :size="16" />
      </template>
      <div class="status-text">
        <span class="status-title">Monitoring worker is failing</span>
        <span class="status-detail">{{ failureSummary }}</span>
      </div>
    </Message>
    <Message v-if="stallSummary" severity="warn" data-testid="worker-stalled">
      <template #icon>
        <Clock :size="16" />
      </template>
      <div class="status-text">
        <span class="status-title">Monitoring worker is behind</span>
        <span class="status-detail">{{ stallSummary }}</span>
      </div>
    </Message>
    <div v-if="facts || recoveredSummary" class="worker-facts" data-testid="worker-health">
      <span class="facts-label">Monitoring worker</span>
      <span v-if="facts">{{ facts }}</span>
      <span v-if="recoveredSummary" class="facts-history" data-testid="worker-incidents">
        {{ recoveredSummary }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Message from 'primevue/message'
import { CircleAlert, Clock, TriangleAlert } from 'lucide-vue-next'
import type { WorkerHealthResponse } from '@/api/monitoring/interfaces'
import {
  getRecordingDetail,
  getRecoveredIncidentsSummary,
  getWorkerFacts,
  getWorkerFailureSummary,
  getWorkerStallSummary,
  isRecordingOff,
} from '@/utils/worker'

interface Props {
  health: WorkerHealthResponse | null
}

const props = defineProps<Props>()

const recordingOff = computed(() => isRecordingOff(props.health))

const recordingDetail = computed(() => getRecordingDetail(props.health))

const failureSummary = computed(() => getWorkerFailureSummary(props.health))

const stallSummary = computed(() => getWorkerStallSummary(props.health))

const facts = computed(() => getWorkerFacts(props.health))

const recoveredSummary = computed(() => getRecoveredIncidentsSummary(props.health))

const hasContent = computed(
  () =>
    recordingOff.value ||
    !!failureSummary.value ||
    !!stallSummary.value ||
    !!facts.value ||
    !!recoveredSummary.value,
)
</script>

<style scoped>
.worker-status {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-title {
  font-size: 14px;
  font-weight: 500;
}

.status-detail {
  font-size: 12px;
}

.worker-facts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.facts-label {
  font-weight: 500;
  color: var(--p-text-color);
}

.facts-history {
  color: var(--p-message-warn-color);
}
</style>
