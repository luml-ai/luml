<template>
  <Message severity="warn" class="stale-notice" role="status">
    <template #icon>
      <Clock :size="16" />
    </template>
    <div class="stale-text">
      <span class="stale-title">Showing a snapshot from before the selected range</span>
      <span class="stale-detail">
        The worker last computed this section at {{ formatTimestamp(computedAt) }}. These numbers
        describe that earlier window, not the selected range. Widen the range or send fresh traffic
        to see current values.
      </span>
    </div>
  </Message>
</template>

<script setup lang="ts">
import Message from 'primevue/message'
import { Clock } from 'lucide-vue-next'
import { formatTimestamp } from '@/utils/format'

interface Props {
  computedAt?: string | null
}

withDefaults(defineProps<Props>(), {
  computedAt: null,
})
</script>

<style scoped>
.stale-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stale-title {
  font-size: 14px;
  font-weight: 500;
}

.stale-detail {
  font-size: 12px;
}
</style>
