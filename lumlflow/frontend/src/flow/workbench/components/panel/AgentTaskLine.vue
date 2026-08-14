<template>
  <div class="flex min-w-0 flex-col gap-1 px-1.5">
    <template v-if="paired">
      <div class="flex min-w-0 items-center gap-2">
        <ActorChip
          :actor="{ kind: 'agent', label: paired.label }"
          :muted="paired.state !== 'working'"
        />
        <BranchTag
          v-if="paired.state === 'working' && paired.branch !== viewedBranch"
          :name="paired.branch"
        />
        <span v-if="paired.state !== 'working'" class="text-base text-muted-color">
          idle{{ paired.idleFor ? ` · ${paired.idleFor}` : '' }}
        </span>
      </div>
      <p v-if="paired.state === 'working' && paired.task" class="min-w-0 text-base">
        {{ paired.task }}
      </p>
    </template>

    <!-- The one place the workbench says there is no agent; the prompt that
         pairs one is behind the link rather than on screen five times over. -->
    <div v-else class="flex items-center gap-1 text-base text-muted-color">
      <span>not paired ·</span>
      <PairLink :prompt="connect" @open="emit('pair')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PairedAgent } from '../../model/types'
import PairLink from '../session/PairLink.vue'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'

// Rendered from the latest transaction's intent — never a fabricated status.
defineProps<{
  paired?: PairedAgent
  viewedBranch: string
  /** The prompt that pairs one, once the daemon has answered for it. */
  connect?: string | null
}>()

const emit = defineEmits<{
  /** The pairing popover opened: this is when a live surface goes and asks. */
  pair: []
}>()
</script>
