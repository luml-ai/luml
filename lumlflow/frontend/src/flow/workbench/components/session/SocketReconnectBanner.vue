<template>
  <Message severity="warn" size="small">
    <template #icon><RefreshCw :size="15" class="shrink-0 animate-spin" /></template>
    <p class="min-w-0 text-base">
      <span class="font-medium">connection dropped. reconnecting</span>
      <span> · replays from cursor</span>
    </p>
  </Message>
</template>

<script setup lang="ts">
import { Message } from 'primevue'
import { RefreshCw } from 'lucide-vue-next'

// A dropped socket is a latency event, never a data event: the cursor replay
// restores everything, so the banner promises exactly that and nothing more.
</script>
