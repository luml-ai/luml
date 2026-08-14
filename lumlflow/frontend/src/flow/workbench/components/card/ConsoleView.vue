<template>
  <div
    class="rounded-lg bg-surface-900 dark:bg-surface-950 p-3 font-mono text-sm leading-relaxed text-surface-200 dark:text-surface-200 overflow-auto max-h-64"
  >
    <div
      v-for="(line, index) in lines"
      :key="index"
      :class="index === lines.length - 1 ? 'animate-pulse' : ''"
    >
      {{ line }}
    </div>
    <div v-if="lines.length === 0" class="text-surface-500 dark:text-surface-500">
      waiting for output…
    </div>
  </div>
</template>

<script setup lang="ts">
/** Terminal-style live stdout/stderr while the cell runs; demotes to logs after. */
defineProps<{ lines: string[] }>()
</script>
