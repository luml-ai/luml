<template>
  <!--
    No token, or one the daemon refused: this tab has no key either way, and
    neither says anything about the server. It comes first because a refusal
    mid-session leaves a workbench whose every gesture would fail.
  -->
  <NotConnectedNotice v-if="source === 'unconnected'" class="max-w-2xl" />

  <LiveWorkbench v-else-if="live" :session="live.session" :stream="live.stream" />

  <!--
    A live source that has not opened yet is not a flow with nothing in it. It
    is a wait, a server that is gone, or a refusal it named — each says which,
    because rendering the fixture here would put another flow's cells on screen
    under this one's name.
  -->
  <div v-else-if="source === 'live'" class="flex flex-col gap-3">
    <DaemonDownBanner v-if="unreachable" />
    <p v-else-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>
    <p v-else class="text-base text-muted-color">opening {{ flowId }}…</p>
  </div>

  <FixtureWorkbench v-else />
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
import FixtureWorkbench from './FixtureWorkbench.vue'
import LiveWorkbench from './LiveWorkbench.vue'

/**
 * Which workbench this is: a live one, the fixture, or none at all.
 *
 * Opening the flow is what attaches the session — there is no connect verb and
 * no kernel picker anywhere, and the kernel still waits for the first gesture
 * that needs one. The switch is decided once, here, so nothing below it has to
 * ask where its data came from.
 */
const route = useRoute()
const token = browserToken()
// A token the daemon refused counts as none: same surface, and still never over
// a fixture that was asked for outright, which the switch decides first.
const source = computed(() => selectSource(route, tokenRejected.value ? null : token))
const flowId = typeof route.params.flowId === 'string' ? route.params.flowId : undefined

const live = shallowRef<{ session: FlowSessionHandle; stream: FlowStream } | null>(null)
const unreachable = ref(false)
const refusal = ref<string | null>(null)

if (source.value === 'live' && token !== null) {
  const stream = new FlowStream({ token })
  // Where this browser got to last time, so the catch-up marker has a gap to
  // measure. Read before attaching — the catch-up is what compares them.
  const storage = browserCursorStorage()
  const session = useFlowSession({
    api: new FlowApi({ token }),
    stream,
    flow: flowId,
    seenStep: flowId ? readCursor(flowId, storage) : null,
  })
  // The session takes the scope's teardown itself: leaving the socket open
  // behind a closed tab is what would keep the server writing to nobody.
  session
    .attach()
    .then(() => {
      live.value = { session, stream }
      if (flowId) {
        watch(session.head, (step) => writeCursor(flowId, step, storage), { immediate: true })
      }
    })
    .catch((failure: unknown) => {
      if (failure instanceof DaemonUnreachable) unreachable.value = true
      else refusal.value = failure instanceof Error ? failure.message : String(failure)
    })
}
</script>
