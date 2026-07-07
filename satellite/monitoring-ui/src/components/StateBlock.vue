<template>
  <div v-if="view === 'loading'" class="state-block" data-testid="state-loading" aria-busy="true">
    <div
      v-for="n in skeletonRows"
      :key="n"
      class="skeleton"
      :style="{ width: `${90 - n * 12}%` }"
    />
  </div>

  <div v-else-if="view === 'error'" class="state-block state-message" data-testid="state-error">
    <TriangleAlert :size="22" class="state-icon danger" />
    <p class="state-title">{{ errorTitle }}</p>
    <p class="state-detail">{{ errorDetail }}</p>
  </div>

  <div v-else-if="view === 'empty'" class="state-block state-message" data-testid="state-empty">
    <Hourglass :size="22" class="state-icon muted" />
    <p class="state-title">{{ emptyTitle }}</p>
    <p class="state-detail">{{ emptyDetail }}</p>
  </div>
</template>

<script setup lang="ts">
import { TriangleAlert, Hourglass } from 'lucide-vue-next'
import type { SectionView } from '@/lib/section'

withDefaults(
  defineProps<{
    view: SectionView
    skeletonRows?: number
    errorTitle?: string
    errorDetail?: string
    emptyTitle?: string
    emptyDetail?: string
  }>(),
  {
    skeletonRows: 3,
    errorTitle: 'Section unavailable',
    errorDetail: 'The monitoring store could not be reached. Other sections are unaffected.',
    emptyTitle: 'Not computed yet',
    emptyDetail: 'The worker has not materialized results for this window yet.',
  },
)
</script>

<style scoped>
.state-block {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-3);
}
.state-message {
  align-items: center;
  text-align: center;
  padding: var(--luml-space-8) var(--luml-space-5);
  color: var(--luml-fg-muted);
}
.skeleton {
  height: 14px;
  border-radius: var(--luml-radius-sm);
  background: linear-gradient(
    90deg,
    var(--luml-surface-100) 25%,
    var(--luml-surface-200) 37%,
    var(--luml-surface-100) 63%
  );
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
.state-icon.danger {
  color: var(--luml-danger);
}
.state-icon.muted {
  color: var(--luml-fg-faint);
}
.state-title {
  margin: var(--luml-space-2) 0 0;
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.state-detail {
  margin: 4px 0 0;
  font-size: var(--luml-caption-size);
}
@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: 0 0;
  }
}
</style>
