<template>
  <Message severity="warn" size="small">
    <template #icon><Unplug :size="15" class="shrink-0" /></template>
    <p class="min-w-0 text-base">
      <span class="font-medium">this tab is not connected.</span>
      <span>
        it has no key, or lumlflow restarted since. open the address
        <code class="font-mono text-sm">lumlflow ui</code> prints.</span
      >
    </p>
  </Message>
</template>

<script setup lang="ts">
import { Message } from 'primevue'
import { Unplug } from 'lucide-vue-next'

/**
 * The tab holds no token the server accepts: it never had one, or a restart
 * minted another and this one was refused. One surface for both, because both
 * end in the same gesture — and neither is a claim that the server is down.
 */
</script>
