<template>
  <Popover ref="popover">
    <div class="flex w-96 flex-col gap-3">
      <p class="text-sm text-muted-color">{{ GESTURE_LINES[gesture] }}</p>
      <CopyBlock :value="payload" label="copy the payload" />
      <div class="flex items-center justify-between gap-3">
        <!-- Handoff-only by design: the agent's session is its own process,
             whatever harness it runs in, and this is the address it is handed. -->
        <p class="flex-1 text-sm text-muted-color">paste it into the paired session</p>
        <Button label="hand off" @click="handOff" />
      </div>
    </div>
  </Popover>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button, Popover } from 'primevue'
import type { FlowCell } from '../../model/types'
import CopyBlock from '../../ui/CopyBlock.vue'
import { buildHandoffPayload, GESTURE_LINES, type HandoffGesture } from './sendToAgent'

/**
 * The payload a handoff hands over, in the overlay that carries it. Its trigger
 * is whatever opened it — a button on the card, a row in the card's menu — so
 * the overlay itself takes the anchor rather than owning one.
 */
const props = defineProps<{
  cell: FlowCell
  gesture: HandoffGesture
  branch?: string
  /** The daemon's payload for this gesture, once it has answered. */
  handoff?: string | null
}>()

const emit = defineEmits<{ 'send-to-agent': [payload: string] }>()

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')

const payload = computed(
  () => props.handoff ?? buildHandoffPayload(props.cell, props.branch ?? 'main', props.gesture),
)

function handOff(): void {
  emit('send-to-agent', payload.value)
  popover.value?.hide()
}

defineExpose({
  toggle: (event: Event) => popover.value?.toggle(event),
  show: (event: Event, target?: unknown) => popover.value?.show(event, target),
  hide: () => popover.value?.hide(),
})
</script>
