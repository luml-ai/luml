<template>
  <Card class="top-features">
    <template #content>
      <div class="header">
        <h3 class="title">Top drifted features</h3>
        <span class="subtitle">population stability index (PSI)</span>
      </div>
      <div v-if="features.length" class="list">
        <div v-for="feature in features" :key="feature.feature" class="row">
          <div class="row-head">
            <span class="name">{{ feature.feature }}</span>
            <span class="psi">
              <span class="psi-label">PSI</span>
              <span>{{ formatPsi(feature.psi) }}</span>
            </span>
          </div>
          <ProgressBar
            :value="getPsiProgress(feature.psi)"
            :show-value="false"
            :dt="{
              height: '6px',
              borderRadius: '6px',
              value: { background: getPsiBarColor(feature.severity) },
            }"
          />
        </div>
      </div>
      <span v-else class="empty">No feature drift in this window.</span>
    </template>
  </Card>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import type { DriftedFeature } from '@/api/monitoring/interfaces'
import { formatPsi, getPsiBarColor, getPsiProgress } from '@/utils/drift'

interface Props {
  features: DriftedFeature[]
}

withDefaults(defineProps<Props>(), {
  features: () => [],
})
</script>

<style scoped>
.top-features {
  border: 1px solid var(--p-content-border-color);
}

.header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 24px;
}

.title {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.subtitle,
.empty {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.psi {
  display: flex;
  flex-shrink: 0;
  gap: 4px;
}

.psi-label {
  color: var(--p-text-muted-color);
}
</style>
