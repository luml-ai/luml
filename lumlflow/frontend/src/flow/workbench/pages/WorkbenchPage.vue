<template>
  <NotConnectedNotice v-if="source === 'unconnected'" class="max-w-2xl" />

  <LiveWorkbench v-else-if="live" :session="live.session" :stream="live.stream" />

  <div v-else class="flex flex-col gap-3">
    <DaemonDownBanner v-if="unreachable" />
    <p v-else-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>
    <p v-else class="text-base text-muted-color">opening {{ flowId }}…</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import { FlowStream } from '@/flow/api/stream'
import { browserToken, tokenRejected } from '@/flow/api/token'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import NotConnectedNotice from '../components/session/NotConnectedNotice.vue'
import { browserCursorStorage, readCursor, writeCursor } from '../live/cursor'
import { selectSource } from '../live/source'
import { useFlowSession } from '../live/useFlowSession'
import type { FlowSessionHandle } from '../live/useFlowSession'
import LiveWorkbench from './LiveWorkbench.vue'

const route = useRoute()
const token = browserToken()
const source = computed(() => selectSource(tokenRejected.value ? null : token))
const flowId = typeof route.params.flowId === 'string' ? route.params.flowId : undefined

const live = shallowRef<{ session: FlowSessionHandle; stream: FlowStream } | null>(null)
const unreachable = ref(false)
const refusal = ref<string | null>(null)

if (source.value === 'live' && token !== null) {
  const stream = new FlowStream({ token })
  const storage = browserCursorStorage()
  const marker = flowId ? readCursor(flowId, storage) : null
  const session = useFlowSession({
    api: new FlowApi({ token }),
    stream,
    flow: flowId,
    seenStep: marker?.step,
    seenFlowId: marker?.flowId,
  })
  session
    .attach()
    .then(() => {
      live.value = { session, stream }
      if (flowId) {
        watch(
          session.head,
          (step) => {
            const identity = session.brief.value?.flow_id
            if (identity) writeCursor(flowId, identity, step, storage)
          },
          { immediate: true },
        )
      }
    })
    .catch((failure: unknown) => {
      if (failure instanceof DaemonUnreachable) unreachable.value = true
      else refusal.value = failure instanceof Error ? failure.message : String(failure)
    })
}
</script>
