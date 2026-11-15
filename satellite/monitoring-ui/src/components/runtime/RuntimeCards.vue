<template>
  <div class="cards">
    <MCard label="Requests" :content="formatOptional(data.request_count, formatInteger)" />
    <MCard label="Success rate" :content="formatOptional(data.success_rate, formatPercent)" />
    <MCard label="Error rate" :content="formatOptional(data.error_rate, formatPercent)" />
    <MCard label="Latency p50" :content="formatOptional(data.latency_p50_ms, formatMs)" />
    <MCard label="Latency p95" :content="formatOptional(data.latency_p95_ms, formatMs)" />
    <MCard label="Latency max" :content="formatOptional(data.latency_max_ms, formatMs)" />
    <MCard label="Timeouts" :content="formatOptional(data.timeout_count, formatInteger)" />
    <MCard
      label="Failed inferences"
      :content="formatOptional(data.failed_inference_count, formatInteger)"
    />
  </div>
</template>

<script setup lang="ts">
import type { RuntimeResponse } from '@/api/monitoring/interfaces'
import MCard from '@/components/MCard.vue'
import { formatInteger, formatMs, formatOptional, formatPercent } from '@/utils/format'

interface Props {
  data: RuntimeResponse
}

defineProps<Props>()
</script>

<style scoped>
.cards {
  --cards-column-gap: 16px;
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(max(260px, (100% - 3 * var(--cards-column-gap)) / 4), 1fr)
  );
  gap: 20px var(--cards-column-gap);
}
</style>
