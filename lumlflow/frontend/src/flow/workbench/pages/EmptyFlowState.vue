<template>
  <div class="flex h-full min-h-0 items-start justify-center overflow-y-auto p-6">
    <div class="flex w-full max-w-xl flex-col gap-3 py-4">
      <h3 class="text-xl font-medium">No cells on <code class="font-mono">main</code> yet</h3>

      <CopyField value="lumlflow cells new load_data" />

      <div class="flex flex-wrap items-center gap-x-1.5 text-base text-muted-color">
        <Button link label="add one here" :pt="LINK_PT" @click="emit('create')" />
        <span>·</span>
        <template v-if="!paired">
          <Button link label="pair an agent" :pt="LINK_PT" @click="emit('pair')" />
          <span>·</span>
        </template>
        <Button link label="agent guide" :pt="LINK_PT" @click="emit('cheatsheet')" />
        <span>·</span>
        <Button link label="notebook view" :pt="LINK_PT" @click="emit('notebook')" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import type { PairedAgent } from '../model/types'
import CopyField from '../ui/CopyField.vue'

// An empty surface gets a heading and one line of options — not a grid of
// cards, not a dashed frame. The command is copyable; everything else is a
// link, and agent setup stays in the left panel.
defineProps<{
  paired?: PairedAgent
}>()

const emit = defineEmits<{
  cheatsheet: []
  notebook: []
  /** Scaffold the first cell through the daemon rather than the terminal. */
  create: []
  pair: []
}>()

const LINK_PT = { root: { class: 'p-0 text-base font-normal' } }
</script>
