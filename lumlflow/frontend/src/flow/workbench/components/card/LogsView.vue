<template>
  <div class="flex flex-col gap-2">
    <RouterLink v-if="tracker?.url" :to="tracker.url" class="link text-sm self-start">
      open experiment in Experiments
    </RouterLink>
    <pre v-if="renderedLogs" :class="blockClass">{{ renderedLogs }}</pre>
    <p v-else class="text-sm text-muted-color">no logs</p>
    <template v-if="error">
      <p class="text-sm text-muted-color">traceback</p>
      <pre :class="blockClass">{{ terminalText(error.traceback) }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { TrackerExperiment } from '@/flow/api/types'
import type { CellErrorInfo } from '../../model/types'
import { terminalText } from '../../model/terminal'

/**
 * Logs of the current materialization; while a cell runs this still holds the
 * previous run's output (the live stream is the console tab). Tracebacks land
 * here for every failure — demotion hides them from the card face, not from logs.
 */
const props = defineProps<{
  logs?: string
  error?: CellErrorInfo
  tracker?: TrackerExperiment
}>()

const renderedLogs = computed(() => terminalText(props.logs ?? '').trimEnd())

const blockClass =
  'font-mono text-sm leading-relaxed rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-3 overflow-auto max-h-64 whitespace-pre-wrap'
</script>
