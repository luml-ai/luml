<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Lanes"
    dismissable-mask
    :style="{ width: 'min(58rem, 94vw)' }"
  >
    <BranchGraph
      :branches="branches"
      :selectable="selectable"
      :worktree-locked="worktreeLocked"
      @view="emit('view', $event)"
      @checkout="(name, force) => emit('checkout', name, force)"
      @archive="emit('archive', $event)"
      @compare="emit('compare', $event)"
    />
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog } from 'primevue'
import type { BranchInfo } from '../../model/types'
import BranchGraph from './BranchGraph.vue'

// Overlay, not a permanent panel: the lane map is consulted at decision
// points, disclosed from the lane identifier.
defineProps<{
  branches: BranchInfo[]
  selectable?: boolean
  worktreeLocked?: boolean
}>()

const emit = defineEmits<{
  view: [name: string]
  /** `force` is the escape past an agent's worktree lock, never the default. */
  checkout: [name: string, force?: boolean]
  archive: [name: string]
  compare: [names: string[]]
}>()

const visible = defineModel<boolean>('visible', { required: true })
</script>
