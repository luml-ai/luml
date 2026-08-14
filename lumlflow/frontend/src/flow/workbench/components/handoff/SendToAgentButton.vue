<template>
  <Button
    v-tooltip.top="label ? undefined : 'send to agent'"
    text
    :rounded="!label"
    :severity="severity ?? 'secondary'"
    :label="label"
    aria-label="send to agent"
    @click="onOpen($event)"
  >
    <template #icon><Send :size="14" /></template>
  </Button>

  <HandoffPopover
    ref="popover"
    :cell="cell"
    :gesture="gesture"
    :branch="branch"
    :handoff="handoff"
    @send-to-agent="emit('send-to-agent', $event)"
  />
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button } from 'primevue'
import { Send } from 'lucide-vue-next'
import type { FlowCell } from '../../model/types'
import HandoffPopover from './HandoffPopover.vue'
import type { HandoffGesture } from './sendToAgent'

/**
 * The address the user never retypes: every card, error, and diff can hand the
 * agent a payload carrying slug, branch, step, and the error when present.
 *
 * The payload itself belongs to the daemon (it holds the traceback of a run no
 * card opened), so a live surface answers `open` with one and passes it in. The
 * local build behind the popover is what the fixtures and the gallery render,
 * and it is the shape the daemon's own answer follows.
 */
const props = defineProps<{
  cell: FlowCell
  gesture?: HandoffGesture
  branch?: string
  /** With a label the trigger is a labeled button ("Fix this"); without, an icon. */
  label?: string
  severity?: string
  /** The daemon's payload for this gesture, once it has answered. */
  handoff?: string | null
}>()

const emit = defineEmits<{
  'send-to-agent': [payload: string]
  /** The popover is opening: this is when a live surface goes and asks. */
  open: [gesture: HandoffGesture]
}>()

const popover = useTemplateRef<InstanceType<typeof HandoffPopover>>('popover')

const gesture = computed<HandoffGesture>(() => props.gesture ?? 'explain')

function onOpen(event: Event): void {
  emit('open', gesture.value)
  popover.value?.toggle(event)
}
</script>
