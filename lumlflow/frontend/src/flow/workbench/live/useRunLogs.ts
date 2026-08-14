/**
 * The live console of one run — channel 2, and durable nowhere.
 *
 * A console tab that opens halfway through a ten-minute run must not be empty,
 * so this starts from a tail rather than from the next chunk: the daemon's ring
 * for a subscription it has not seen before, this client's ring for a run it
 * was already buffering. Both are bounded, both are the tail and never the
 * whole run — the capped log artifact on the materialization is what the *logs*
 * tab replays once the run has ended, and that is a different surface.
 *
 * Chunks carry one monotonic `seq` across stdout and stderr, so interleaving is
 * the daemon's order and not a guess made here.
 */

import { computed, getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type { LogFrame, StreamFrame } from '@/flow/api/types'
import type { FlowStream } from '@/flow/api/stream'
import type { FlowSessionHandle } from './useFlowSession'

export interface RunLogsHandle {
  chunks: Ref<LogFrame[]>
  /** The console's text, ANSI preserved exactly as the run wrote it. */
  text: ComputedRef<string>
}

export function useRunLogs(
  session: FlowSessionHandle,
  stream: FlowStream,
  runId: Ref<string | null>,
): RunLogsHandle {
  const chunks = ref<LogFrame[]>([])

  const unlisten = stream.onFrame((frame: StreamFrame) => {
    if (!('channel' in frame) || frame.channel !== 'logs') return
    if (frame.run_id !== runId.value || frame.flow !== session.path.value) return
    chunks.value = [...chunks.value, frame]
  })

  watch(
    [runId, session.path],
    ([id, flow], previous) => {
      const [wasId, wasFlow] = previous ?? [null, '']
      if (wasId && wasFlow) stream.unwatchRun(wasFlow, wasId)
      if (!id || !flow) {
        chunks.value = []
        return
      }
      stream.watchRun(flow, id)
      chunks.value = stream.tail(flow, id)
    },
    { immediate: true },
  )

  if (getCurrentScope()) {
    onScopeDispose(() => {
      unlisten()
      const id = runId.value
      if (id && session.path.value) stream.unwatchRun(session.path.value, id)
    })
  }

  return {
    chunks,
    text: computed(() => chunks.value.map((chunk) => chunk.text).join('')),
  }
}
