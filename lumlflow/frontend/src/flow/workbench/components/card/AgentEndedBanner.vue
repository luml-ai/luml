<template>
  <Message severity="warn" size="small" :pt="BANNER_PT">
    <template #icon><Bot :size="14" class="shrink-0" /></template>
    <span class="min-w-0 flex-1 truncate text-base" v-html="line" />
    <SendToAgentButton
      :cell="cell"
      :branch="branch ?? 'main'"
      :gesture="failedRun ? 'fix' : 'explain'"
      label="hand off"
      :handoff="handoff"
      @open="emit('handoff', $event)"
      @send-to-agent="emit('send-to-agent', $event)"
    />
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Message } from 'primevue'
import { Bot } from 'lucide-vue-next'
import type { HandoffGesture } from '@/flow/api/types'
import { formatCount } from '../../model/format'
import type { FlowCell } from '../../model/types'
import SendToAgentButton from '../handoff/SendToAgentButton.vue'
import { inlineCodeHtml } from './inlineCode'

/**
 * A state, not a toast: anchored under the last cell the agent touched when its
 * session ended with work outstanding. Says what is outstanding, never why the
 * session ended, because that is not recorded.
 */
const props = defineProps<{
  cell: FlowCell
  branch?: string
  failedRun?: boolean
  unsyncedAssets?: number
  /** The daemon's payload for whichever gesture the outstanding work calls for. */
  handoff?: string | null
}>()

const emit = defineEmits<{
  'send-to-agent': [payload: string]
  handoff: [gesture: HandoffGesture]
}>()

const BANNER_PT = { content: { class: 'w-full gap-2 py-1' } }

const line = computed(() => {
  const parts: string[] = []
  if (props.failedRun) parts.push(`a failed run on \`${props.cell.slug}\``)
  if (props.unsyncedAssets) parts.push(formatCount(props.unsyncedAssets, 'stale asset'))
  const outstanding = parts.length ? parts.join(' · ') : 'nothing outstanding'
  return inlineCodeHtml(`agent session ended · ${outstanding}`)
})
</script>
