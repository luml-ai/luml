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
    <!--
      Full-basis so the note takes a line of its own rather than trailing its
      subject; the reading width is set inside, because a max-width on the flex
      item itself would let it fit beside the subject and never wrap.
    -->
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

/**
 * A note that is not on screen until it is asked for. The default view of a
 * surface carries the control and its state; the reason behind it lives here,
 * one deliberate click away and reachable from the keyboard.
 *
 * The root box is `display: contents`, so the toggle and the note are laid out
 * by the host: drop it in a `flex flex-wrap` row and the toggle sits beside its
 * subject while the note wraps to its own full-width line under it.
 */
withDefaults(
  defineProps<{
    /** Visible text beside the ⓘ; empty renders the glyph alone. */
    label?: string
    /** What the note is about, for the button's accessible name. */
    subject?: string
  }>(),
  { label: 'why', subject: '' },
)

const open = ref(false)
const buttonId = useId()
const noteId = useId()

const TOGGLE_PT = { root: { class: 'p-0 text-sm font-normal' } }
</script>
