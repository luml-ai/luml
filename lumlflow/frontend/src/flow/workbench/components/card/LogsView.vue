<template>
  <div class="flex flex-col gap-2">
    <pre v-if="logs" :class="blockClass">{{ logs.trimEnd() }}</pre>
    <p v-else class="text-sm text-muted-color">no logs</p>
    <template v-if="error">
      <p class="text-sm text-muted-color">traceback</p>
      <pre :class="blockClass">{{ error.traceback }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { CellErrorInfo } from '../../model/types'

/**
 * Logs of the current materialization; while a cell runs this still holds the
 * previous run's output (the live stream is the console tab). Tracebacks land
 * here for every failure — demotion hides them from the card face, not from logs.
 */
defineProps<{ logs?: string; error?: CellErrorInfo }>()

const blockClass =
  'font-mono text-sm leading-relaxed rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-3 overflow-auto max-h-64 whitespace-pre-wrap'
</script>
