<template>
  <div
    class="rounded-lg bg-surface-900 dark:bg-surface-950 p-3 font-mono text-sm leading-relaxed text-surface-200 dark:text-surface-200 overflow-auto max-h-64"
  >
    <div
      v-for="(line, index) in renderedLines"
      :key="index"
      :class="index === renderedLines.length - 1 ? 'animate-pulse' : ''"
    >
      {{ line }}
    </div>
    <div v-if="renderedLines.length === 0" class="text-surface-500 dark:text-surface-500">
      waiting for output…
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { terminalText } from '../../model/terminal'

/** Terminal-style live stdout/stderr while the cell runs; demotes to logs after. */
const props = defineProps<{ lines: string[] }>()

const renderedLines = computed(() => {
  if (props.lines.length === 0) return []
  return terminalText(props.lines.join('\n')).split('\n')
})
</script>
