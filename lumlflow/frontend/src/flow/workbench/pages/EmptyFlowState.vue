<template>
  <div class="flex h-full min-h-0 items-start justify-center overflow-y-auto p-6">
    <div class="flex w-full max-w-xl flex-col gap-3 py-4">
      <h3 class="text-xl font-medium">No cells on <code class="font-mono">main</code> yet</h3>

      <CopyField value="lumlflow cells new load_data" />

      <div class="flex flex-wrap items-center gap-x-1.5 text-base text-muted-color">
        <Button link label="add one here" :pt="LINK_PT" @click="emit('create')" />
        <span>·</span>
        <template v-if="!paired">
          <PairLink :prompt="connect" @open="emit('pair')" />
          <span>·</span>
        </template>
        <Button link label="AGENTS.md" :pt="LINK_PT" @click="emit('cheatsheet')" />
        <span>·</span>
        <Button link label="notebook view" :pt="LINK_PT" @click="emit('notebook')" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import PairLink from '../components/session/PairLink.vue'
import type { PairedAgent } from '../model/types'
import CopyField from '../ui/CopyField.vue'

// An empty surface gets a heading and one line of options — not a grid of
// cards, not a dashed frame. The command is copyable; everything else is a
// link, and the prompt that pairs an agent lives behind one of them.
defineProps<{
  paired?: PairedAgent
  /** The prompt that pairs one, once the daemon has answered for it. */
  connect?: string | null
}>()

const emit = defineEmits<{
  cheatsheet: []
  notebook: []
  /** Scaffold the first cell through the daemon rather than the terminal. */
  create: []
  /** The pairing popover opened: this is when a live surface goes and asks. */
  pair: []
}>()

const LINK_PT = { root: { class: 'p-0 text-base font-normal' } }
</script>
