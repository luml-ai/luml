<template>
  <div v-if="recordingOff || failureSummary" class="worker-status">
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Message from 'primevue/message'
import { CircleAlert, TriangleAlert } from 'lucide-vue-next'
import type { WorkerHealthResponse } from '@/api/monitoring/interfaces'
import { getRecordingDetail, getWorkerFailureSummary, isRecordingOff } from '@/utils/worker'

interface Props {
  health: WorkerHealthResponse | null
}

const props = defineProps<Props>()

const recordingOff = computed(() => isRecordingOff(props.health))

const recordingDetail = computed(() => getRecordingDetail(props.health))

const failureSummary = computed(() => getWorkerFailureSummary(props.health))
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
</style>
