<template>
  <span class="inline-flex">
    <Button
      :label="label"
      link
      :pt="LINK_PT"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="toggle"
    />
    <Popover ref="popover" @show="open = true" @hide="open = false">
      <!-- Wide enough for the prompt's own 72-column wrapping: re-wrapping it
           breaks the config snippet's shape, which is the part being read. -->
      <CopyBlock
        class="w-[41rem]"
        :value="prompt ?? CONNECT_PROMPT"
        label="copy the connect prompt"
      />
    </Popover>
  </span>
</template>

<script setup lang="ts">
import { ref, useTemplateRef } from 'vue'
import { Button, Popover } from 'primevue'
import CopyBlock from '../../ui/CopyBlock.vue'
import { CONNECT_PROMPT } from './connectPrompt'

/**
 * Pairing, said once: a link, and behind it the one thing the reader hands to
 * an agent. The agent connects back over what the prompt registers, and that
 * connection *is* the session — so this stays one-directional, detecting the
 * `agent_begin` transaction rather than confirming anything.
 *
 * The prompt is the daemon's, for the same reason a handoff payload is: it
 * names the workspace, the branch the files hold and the executable a config
 * can spawn. `open` is when a live surface goes and asks for it; the local one
 * behind it is what the fixtures and the gallery render.
 */
withDefaults(
  defineProps<{
    label?: string
    /** The daemon's prompt, once it has answered. */
    prompt?: string | null
  }>(),
  { label: 'pair an agent', prompt: null },
)

const emit = defineEmits<{ open: [] }>()

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')
const open = ref(false)

const LINK_PT = { root: { class: 'p-0 text-base font-normal' } }

// The ask rides the gesture at the link rather than the overlay's own `show`,
// which is the same place `SendToAgentButton` puts it: `aria-expanded` follows
// the overlay because an outside click closes it without coming back here, and
// a read nobody looks at costs less than a prompt that opens empty.
function toggle(event: Event): void {
  emit('open')
  popover.value?.toggle(event)
}
</script>
