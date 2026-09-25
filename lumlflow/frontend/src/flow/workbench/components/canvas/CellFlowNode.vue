<template>
  <Handle type="target" :position="Position.Left" class="opacity-0" />
  <div
    class="rounded-lg"
    :class="tinted ? 'ring-1 ring-(--p-message-warn-color)' : ''"
    @pointerdown.capture="emit('press')"
  >
    <slot />
  </div>
  <Handle type="source" :position="Position.Right" class="opacity-0" />
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

/**
 * A node's frame: the wiring handles the edges attach to, and the subdued ring
 * the transitive-staleness filter draws. What sits inside is a card, and which
 * card — the fixture's or one bound to the session — is the canvas's caller's
 * to say.
 */
defineProps<{
  /** Transitive-staleness filter is on and this cell is stale under it. */
  tinted?: boolean
}>()

const emit = defineEmits<{ press: [] }>()
</script>
