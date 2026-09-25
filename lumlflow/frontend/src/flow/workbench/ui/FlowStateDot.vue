<template>
  <span v-tooltip.bottom="tooltip" class="inline-flex items-center gap-2 text-base">
    <span class="relative flex h-2.5 w-2.5">
      <span
        v-if="state === 'running'"
        class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
        :style="{ background: color }"
      />
      <span class="relative inline-flex h-2.5 w-2.5 rounded-full" :style="{ background: color }" />
    </span>
    <span v-if="!dotOnly" :class="state === 'daemon-down' ? 'text-(--p-message-error-color)' : ''">
      {{ label }}
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FlowState } from '../model/types'

/** The five-state flow indicator — running/stopped alone would not be honest. */
const props = defineProps<{ state: FlowState; dotOnly?: boolean }>()

const CONFIG: Record<FlowState, { label: string; tooltip: string; dot: string }> = {
  running: {
    label: 'running',
    tooltip: 'a run is in flight',
    dot: 'var(--p-message-success-color)',
  },
  idle: { label: 'idle', tooltip: 'paired, nothing running', dot: 'var(--p-message-info-color)' },
  unpaired: {
    label: 'unpaired',
    tooltip: 'no agent registered. everything still works.',
    dot: 'var(--p-text-muted-color)',
  },
  'kernel-not-started': {
    label: 'kernel not started',
    tooltip: 'browsing works from previews. expanding a value starts the kernel.',
    dot: 'var(--p-text-muted-color)',
  },
  'daemon-down': {
    label: 'not running',
    tooltip: 'nothing live. showing last-known state.',
    dot: 'var(--p-message-error-color)',
  },
}

const label = computed(() => CONFIG[props.state].label)
const tooltip = computed(() => CONFIG[props.state].tooltip)
const color = computed(() => CONFIG[props.state].dot)
</script>
