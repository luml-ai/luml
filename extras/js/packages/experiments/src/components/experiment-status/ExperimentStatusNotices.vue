<template>
  <div v-if="notices.length" class="notices">
    <Message
      v-for="notice in notices"
      :key="notice.modelId"
      :severity="notice.severity"
      size="small"
      :closable="false"
      data-testid="experiment-status-notice"
      :data-code="notice.code"
    >
      <b>{{ notice.name }}:</b> {{ notice.text }}
    </Message>
  </div>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '@/interfaces/interfaces'
import type { ExperimentSnapshotStatus } from '@/metric-buckets/types'
import { computed } from 'vue'
import { Message } from 'primevue'
import { experimentStatusNotice } from './experimentStatusNotice'

type Props = {
  statuses: ExperimentSnapshotStatus[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const notices = computed(() =>
  props.statuses.flatMap((status) => {
    const notice = experimentStatusNotice(status)
    if (!notice) return []
    const name = props.modelsInfo[status.modelId]?.name ?? 'An experiment'
    return [{ modelId: status.modelId, name, ...notice }]
  }),
)
</script>

<style scoped>
.notices {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
