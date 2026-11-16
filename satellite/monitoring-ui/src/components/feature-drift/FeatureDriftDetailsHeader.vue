<template>
  <div class="details-header">
    <Tag class="feature-tag" severity="secondary">
      <MEllipsis :text="detail.feature" />
    </Tag>
    <div class="details-actions">
      <span class="meta">
        <span class="psi">{{ formatPsiLabel(detail.psi) }}</span>
        <Tag
          :value="getSeverityLabel(detail.status)"
          :severity="getSeverityTagSeverity(detail.status)"
          :dt="STATUS_TAG_TOKENS"
        />
      </span>
      <Button
        label="Reference profile"
        severity="secondary"
        variant="outlined"
        @click="emit('open-reference')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button, Tag } from 'primevue'
import type { FeatureDriftDetail } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatPsiLabel } from '@/utils/drift'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  detail: FeatureDriftDetail
}

defineProps<Props>()

const emit = defineEmits<{
  'open-reference': []
}>()
</script>

<style scoped>
.details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.feature-tag {
  min-width: 0;
  max-width: 100%;
}

.details-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.meta {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.psi {
  font-size: 12px;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}
</style>
