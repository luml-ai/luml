<template>
  <div class="details-header">
    <div class="feature">
      <Tag class="feature-tag" severity="secondary">
        <MEllipsis :text="detail.feature" />
      </Tag>
      <span v-if="detail.distribution?.kind" class="kind">{{ detail.distribution.kind }}</span>
    </div>
    <div class="details-actions">
      <span class="meta">
        <span class="psi">{{ formatPsiLabel(detail.psi) }}</span>
        <Tag
          :value="getSeverityLabel(detail.status)"
          :severity="getSeverityTagSeverity(detail.status)"
          :dt="STATUS_TAG_TOKENS"
        />
      </span>
      <FeatureReferenceProfile :feature="detail.feature" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import type { FeatureDriftDetail } from '@/api/monitoring/interfaces'
import { STATUS_TAG_TOKENS } from '@/constants/drift'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import { formatPsiLabel } from '@/utils/drift'
import MEllipsis from '@/components/MEllipsis.vue'
import FeatureReferenceProfile from '@/components/feature-drift/FeatureReferenceProfile.vue'

interface Props {
  detail: FeatureDriftDetail
}

defineProps<Props>()
</script>

<style scoped>
.details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.feature {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.feature-tag {
  min-width: 0;
  max-width: 100%;
}

.kind {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--p-text-muted-color);
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
