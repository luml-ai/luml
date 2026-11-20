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
      <div class="footer">
        <span class="count">{{ formatPredictionsCount(data.count) }}</span>
        <span
          v-if="data.psi_delta != null"
          class="delta"
          :class="`delta--${getDeltaTone(data.psi_delta)}`"
        >
          {{ formatSignedDelta(data.psi_delta, formatPsi) }} vs
          {{ getCompareTargetLabel(filtersStore.compare) }}
        </span>
      </div>
    </template>
  </MCard>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import type { OutputDriftResponse } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatPsi, formatPsiValue } from '@/utils/drift'
import { formatSignedDelta, getDeltaTone } from '@/utils/format'
import { getCompareTargetLabel } from '@/utils/cards'
import { formatPredictionsCount, getOutputPsiLabel } from '@/utils/output-drift'
import { useFiltersStore } from '@/store/filters'
import MCard from '@/components/MCard.vue'

interface Props {
  data: OutputDriftResponse
}

defineProps<Props>()

const filtersStore = useFiltersStore()
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

.footer {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.count {
  color: var(--p-text-muted-color);
}

.delta--up {
  color: var(--p-message-error-color);
}

.delta--down {
  color: var(--p-message-success-color);
}
</style>
