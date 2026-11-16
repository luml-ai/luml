<template>
  <MCard class="psi-card" :label="getOutputPsiLabel(data.name)">
    <div class="value">
      <span class="psi">{{ formatPsiValue(data.psi) }}</span>
      <Tag
        v-if="data.psi != null"
        :value="getSeverityLabel(data.severity)"
        :severity="getSeverityTagSeverity(data.severity)"
        :dt="STATUS_TAG_TOKENS"
      />
    </div>
    <template #footer>
      <span class="count">{{ formatPredictionsCount(data.count) }}</span>
    </template>
  </MCard>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import type { OutputDriftResponse } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatPsiValue } from '@/utils/drift'
import { formatPredictionsCount, getOutputPsiLabel } from '@/utils/output-drift'
import MCard from '@/components/MCard.vue'

interface Props {
  data: OutputDriftResponse
}

defineProps<Props>()
</script>

<style scoped>
.psi-card {
  align-self: flex-start;
}

.value {
  display: flex;
  align-items: center;
  gap: 8px;
}

.psi {
  font-size: 24px;
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}

.count {
  color: var(--p-text-muted-color);
}
</style>
