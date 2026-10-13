<template>
  <span v-tooltip.bottom="tooltip" class="marker">
    <span class="marker-dot" :class="{ 'marker-dot--running': kernel === 'running' }" />
    <span v-if="label" class="marker-label">{{ label }}</span>
    <Bot v-if="agents" :size="14" class="marker-agent" />
  </span>
</template>

<script setup lang="ts">
import type { KernelState } from '@/api/slices/workspace/workspace.interface'
import { Bot } from 'lucide-vue-next'
import { computed } from 'vue'
import { formatUpdatedAgo } from '@/helpers/date'

interface Props {
  kernel: KernelState
  /** The flow's active runs, shown beside the dot when there are any. */
  label?: number
  /** Open flows summed up by a folder's marker; named in the tooltip only. */
  flows?: number
  agents?: number
  lastActivity?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  label: 0,
  flows: 0,
  agents: 0,
  lastActivity: null,
})

function plural(amount: number, noun: string): string {
  return `${amount} ${noun}${amount === 1 ? '' : 's'}`
}

const tooltip = computed(() => {
  const running = props.kernel === 'running'
  const parts = props.flows
    ? [plural(props.flows, 'open flow'), running ? 'kernel running' : null]
    : [`Kernel ${props.kernel}`]
  if (props.label) parts.push(plural(props.label, 'run'))
  if (props.agents) parts.push(plural(props.agents, 'agent'))
  if (props.lastActivity) parts.push(formatUpdatedAgo(props.lastActivity))
  return parts.filter(Boolean).join(' · ')
})
</script>

<style scoped>
@reference "@/assets/css/index.css";

.marker {
  @apply inline-flex items-center gap-1.5 shrink-0 text-xs text-muted-color;
}
.marker-dot {
  @apply w-2 h-2 rounded-full bg-(--p-surface-400);
}
.marker-dot--running {
  @apply bg-(--p-badge-success-background) shadow-[0px_0px_6px_0px_#22C55E80];
}
.marker-label {
  @apply tabular-nums;
}
</style>
