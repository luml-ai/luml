<template>
  <header class="dash-header" data-testid="dashboard-header">
    <div class="title-row">
      <h1 class="name mono" data-testid="deployment-name">{{ header.name ?? 'Deployment' }}</h1>
      <span v-if="header.status" class="status-pill" :class="statusClass">
        <span class="dot" />
        {{ header.status }}
      </span>
    </div>

    <p class="meta">
      <span v-for="(part, index) in metaParts" :key="index">
        <span v-if="index > 0" class="sep">·</span>
        <span :class="{ mono: part.mono }">{{ part.text }}</span>
      </span>
    </p>

    <a
      v-if="header.inference_url"
      class="inference-url"
      :href="header.inference_url"
      target="_blank"
      rel="noreferrer"
      data-testid="inference-url"
    >
      <LinkIcon :size="14" />
      Inference URL
    </a>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Link as LinkIcon } from 'lucide-vue-next'
import type { HeaderResponse } from '@/api/types'
import { formatTimestamp } from '@/lib/format'

const props = defineProps<{ header: HeaderResponse }>()

const statusClass = computed(() => {
  const status = (props.header.status ?? '').toLowerCase()
  if (status === 'active' || status === 'running') return 'ok'
  if (status === 'error' || status === 'failed') return 'danger'
  return 'muted'
})

const metaParts = computed(() => {
  const parts: { text: string; mono?: boolean }[] = []
  if (props.header.task_type) parts.push({ text: props.header.task_type })
  if (props.header.environment) parts.push({ text: props.header.environment })
  if (props.header.satellite) parts.push({ text: props.header.satellite, mono: true })
  if (props.header.model_name) parts.push({ text: props.header.model_name, mono: true })
  const lastPrediction = formatTimestamp(props.header.last_prediction_at)
  if (lastPrediction) parts.push({ text: `last prediction ${lastPrediction}` })
  return parts
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
.meta {
  margin: 0;
  font-size: 13.5px;
  color: var(--luml-fg-muted);
}
.meta .sep {
  margin: 0 7px;
  color: var(--luml-fg-faint);
}
.inference-url {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: var(--luml-space-1);
  padding: 6px 12px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
}
.inference-url:hover {
  background: var(--luml-bg-hover);
}
</style>
