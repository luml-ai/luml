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

defineProps<{
  tinted?: boolean
}>()

const emit = defineEmits<{ press: [] }>()
</script>
