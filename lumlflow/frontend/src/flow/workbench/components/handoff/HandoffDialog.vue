<template>
  <Dialog
    :visible="visible"
    modal
    :header="header"
    :style="{ width: '38rem' }"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-muted-color">{{ gestureLine }}</p>

      <p v-if="pending" class="text-base text-muted-color">building the payload…</p>
      <p v-else-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>
      <CopyBlock v-else-if="payload" :value="payload" label="copy the payload" />

      <div v-if="payload" class="flex items-center justify-between gap-3">
        <!-- Handoff-only by design: the agent runs in the user's own terminal. -->
        <p class="flex-1 text-sm text-muted-color">paste it into the paired session</p>
        <Button label="hand off" @click="emit('hand-off', payload)" />
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button, Dialog } from 'primevue'
import type { HandoffGesture } from '@/flow/api/types'
import CopyBlock from '../../ui/CopyBlock.vue'
import { GESTURE_LINES } from './sendToAgent'

/**
 * The handoff for the gestures that are not about one cell: summarize this
 * lane, explain this diff. Same payload contract as the card's popover (the
 * daemon builds it), in the one shape a lane-wide ask can be read in.
 */
const props = defineProps<{
  visible: boolean
  gesture: HandoffGesture
  /** Null while the daemon is still building it. */
  payload: string | null
  pending?: boolean
  refusal?: string | null
}>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  'hand-off': [payload: string]
}>()

const HEADERS: Record<HandoffGesture, string> = {
  fix: 'Fix this',
  explain: 'Explain this',
  diff: 'Explain this diff',
  summarize: 'Summarize this lane',
}

const header = computed(() => HEADERS[props.gesture])

const gestureLine = computed(() => GESTURE_LINES[props.gesture])
</script>
