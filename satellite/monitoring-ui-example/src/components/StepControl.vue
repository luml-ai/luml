<template>
  <!--
    Series bucket width. It sits by the runtime charts rather than in the global
    controls because that is all it affects — tables, cards and drift views ignore it.
  -->
  <div class="step" data-testid="step-control">
    <span class="step-label">Step</span>
    <div class="segmented" role="group" aria-label="Series step">
      <button
        v-for="option in options"
        :key="option"
        type="button"
        class="segment"
        :class="{ active: granularity === option }"
        :data-testid="`granularity-${option}`"
        @click="$emit('update:granularity', option)"
      >
        {{ option }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Granularity } from '@/api/types'

defineProps<{ granularity: Granularity }>()
defineEmits<{ 'update:granularity': [Granularity] }>()

const options = [Granularity.AUTO, Granularity.HOUR, Granularity.DAY]
</script>

<style scoped>
.step {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
}
.step-label {
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  overflow: hidden;
  background: var(--luml-bg-card);
}
.segment {
  border: none;
  background: transparent;
  padding: 4px 10px;
  font: inherit;
  font-size: 12px;
  color: var(--luml-fg);
  cursor: pointer;
  text-transform: capitalize;
}
.segment + .segment {
  border-left: 1px solid var(--luml-border);
}
.segment.active {
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font-weight: 500;
}
</style>
