<template>
  <span class="contents">
    <Button
      :id="buttonId"
      link
      size="small"
      :pt="TOGGLE_PT"
      :aria-expanded="open"
      :aria-controls="noteId"
      :aria-label="`${open ? 'hide' : 'show'} note: ${subject || label || 'note'}`"
      @click.stop="open = !open"
    >
      <template #icon><Info :size="14" class="shrink-0" /></template>
      <span v-if="label">{{ label }}</span>
    </Button>
    <p
      v-show="open"
      :id="noteId"
      role="region"
      :aria-labelledby="buttonId"
      class="basis-full text-sm leading-relaxed text-muted-color"
    >
      <span class="block max-w-prose"><slot /></span>
    </p>
  </span>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'
import { Button } from 'primevue'
import { Info } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    label?: string
    subject?: string
  }>(),
  { label: 'why', subject: '' },
)

const open = ref(false)
const buttonId = useId()
const noteId = useId()

const TOGGLE_PT = { root: { class: 'p-0 text-sm font-normal' } }
</script>
