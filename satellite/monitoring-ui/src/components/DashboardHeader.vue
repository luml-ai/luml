<template>
  <header class="dash-header" data-testid="dashboard-header">
    <div class="title-row">
      <h1 class="name mono" data-testid="deployment-name">{{ header.name ?? 'Deployment' }}</h1>
      <span v-if="header.status" class="status-pill" :class="statusClass">
        <span class="dot" />
        {{ header.status }}
      </span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HeaderResponse } from '@/api/types'

const props = defineProps<{ header: HeaderResponse }>()

const statusClass = computed(() => {
  const status = (props.header.status ?? '').toLowerCase()
  if (status === 'active' || status === 'running') return 'ok'
  if (status === 'error' || status === 'failed') return 'danger'
  return 'muted'
})
</script>

<style scoped>
.dash-header {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-2);
}
.title-row {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
  flex-wrap: wrap;
}
.name {
  margin: 0;
  font-size: var(--luml-text-2xl);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--luml-fg-strong);
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-pill .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.status-pill.ok {
  background: var(--luml-success-tint-bg);
  color: var(--luml-success-tint-fg);
}
.status-pill.danger {
  background: var(--luml-danger-tint-bg);
  color: var(--luml-danger-tint-fg);
}
.status-pill.muted {
  background: var(--luml-surface-100);
  color: var(--luml-fg-muted);
}
</style>
