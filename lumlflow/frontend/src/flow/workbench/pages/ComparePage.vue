<template>
  <!-- No token, or one the daemon refused: this tab has no key either way. -->
  <NotConnectedNotice v-if="source === 'unconnected'" class="max-w-2xl" />

  <LiveCompare v-else-if="live" :session="live" />

  <!--
    A live source that has not opened yet is not a comparison with nothing in
    it: it is a wait, a server that is gone, or a refusal it named. Falling back
    to the fixture here would put another flow's sweep on screen.
  -->
  <div v-else-if="source === 'live'" class="flex flex-col gap-3">
    <DaemonDownBanner v-if="unreachable" />
    <p v-else-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>
    <p v-else class="text-base text-muted-color">opening {{ flowId }}…</p>
  </div>

  <FixtureCompare v-else />
</template>

<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import { FlowStream } from '@/flow/api/stream'
import { browserToken, tokenRejected } from '@/flow/api/token'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import NotConnectedNotice from '../components/session/NotConnectedNotice.vue'
import { selectSource } from '../live/source'
import { useFlowSession } from '../live/useFlowSession'
import type { FlowSessionHandle } from '../live/useFlowSession'
import FixtureCompare from './FixtureCompare.vue'
import LiveCompare from './LiveCompare.vue'

/**
 * Which comparison this is: a live one, the fixture, or none at all. The same
 * switch the workbench makes, decided once here so nothing below has to ask.
 */
const route = useRoute()
const token = browserToken()
// A token the daemon refused counts as none, the same way the workbench reads it.
const source = computed(() => selectSource(route, tokenRejected.value ? null : token))
const flowId = typeof route.params.flowId === 'string' ? route.params.flowId : undefined

const live = shallowRef<FlowSessionHandle | null>(null)
const unreachable = ref(false)
const refusal = ref<string | null>(null)

if (source.value === 'live' && token !== null) {
  const stream = new FlowStream({ token })
  const session = useFlowSession({ api: new FlowApi({ token }), stream, flow: flowId })
  session
    .attach()
    .then(() => {
      live.value = session
    })
    .catch((failure: unknown) => {
      if (failure instanceof DaemonUnreachable) unreachable.value = true
      else refusal.value = failure instanceof Error ? failure.message : String(failure)
    })
}
</script>
