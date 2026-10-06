<template>
  <div v-if="shown.length" class="flex flex-col gap-2">
    <DaemonDownBanner v-if="is('daemon-down')" />
    <SocketReconnectBanner v-if="is('socket-dropped')" />

    <Message v-if="is('socket-refused')" severity="error" size="small">
      <template #icon><ShieldOff :size="15" class="shrink-0" /></template>
      <p class="min-w-0 text-base">
        <span class="font-medium">this workspace refused the tab.</span>
        <span>
          lumlflow restarted since this page opened. reopen it with
          <code class="font-mono text-sm">lumlflow ui</code>.</span
        >
      </p>
    </Message>

    <CatchUpMarker v-if="is('behind-cursor')" :count="changesBehind" @open="emit('open-catchup')" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Message } from 'primevue'
import { ShieldOff } from 'lucide-vue-next'
import type { DegradedKind } from '../../live/degraded'
import CatchUpMarker from './CatchUpMarker.vue'
import DaemonDownBanner from './DaemonDownBanner.vue'
import SocketReconnectBanner from './SocketReconnectBanner.vue'

const props = defineProps<{
  degraded: DegradedKind[]
  changesBehind: number
}>()

const emit = defineEmits<{ 'open-catchup': [] }>()

type BannerKind = Exclude<DegradedKind, 'kernel-not-started'>

const shown = computed<BannerKind[]>(() =>
  props.degraded.filter((kind): kind is BannerKind => kind !== 'kernel-not-started'),
)

function is(kind: BannerKind): boolean {
  return shown.value.includes(kind)
}
</script>
