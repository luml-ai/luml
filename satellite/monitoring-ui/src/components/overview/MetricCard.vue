<template>
  <div class="metric-card card" :class="`tone-${tone}`" data-testid="metric-card">
    <div class="label eyebrow">{{ card.label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="detail" class="detail" :class="{ mono: detailMono }">{{ detail }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Card } from '@/api/types'
import { cardDetail, cardTone, formatCardValue } from '@/lib/format'

const props = defineProps<{ card: Card }>()

const value = computed(() => formatCardValue(props.card))
const detail = computed(() => cardDetail(props.card))
const tone = computed(() => cardTone(props.card))
const detailMono = computed(() => props.card.key === 'drifted_features')
</script>

<style scoped>
.metric-card {
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.value {
  font-size: 25px;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--luml-fg-strong);
}
.detail {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.tone-danger {
  border-color: var(--luml-danger-tint-bg);
}
.tone-danger .label,
.tone-danger .value,
.tone-danger .detail {
  color: var(--luml-danger-tint-fg);
}
.tone-warning .detail {
  color: var(--luml-warn-tint-fg);
}
</style>
