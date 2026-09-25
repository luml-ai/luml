<template>
  <Message severity="error" size="small">
    <template #icon><ServerOff :size="15" class="shrink-0" /></template>
    <div class="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5">
      <!--
        The space is interpolated, not typed: the template compiler condenses
        a whitespace-only node between two elements away, and the two
        sentences ran together on screen while reading correctly in source.
      -->
      <p class="min-w-0 text-base">
        <span class="font-medium">lumlflow is not running.</span>
        <span>{{ ' ' }}{{ detail }}</span>
      </p>
      <p v-if="logPath" class="min-w-0 basis-full text-sm text-muted-color">
        daemon log <code class="font-mono">{{ logPath }}</code>
      </p>
      <div class="min-w-56 flex-1"><CopyField value="lumlflow ui" /></div>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { Message } from 'primevue'
import { ServerOff } from 'lucide-vue-next'
import { browserDaemonLog } from '@/flow/api/token'
import CopyField from '../../ui/CopyField.vue'

/**
 * Nobody answered the last round-trip. The remedy is the command, so it is on
 * screen and copyable rather than described.
 */
withDefaults(
  defineProps<{
    /** What this surface has left to show meanwhile — a listing has none. */
    detail?: string
  }>(),
  { detail: 'showing last-known state' },
)

const logPath = browserDaemonLog()
</script>
