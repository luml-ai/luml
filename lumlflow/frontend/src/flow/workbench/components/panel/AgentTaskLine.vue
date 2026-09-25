<template>
  <div class="flex min-w-0 flex-col gap-1 px-1.5">
    <template v-if="paired">
      <div class="flex min-w-0 items-center gap-2">
        <ActorChip
          :actor="{ kind: 'agent', label: paired.label }"
          :muted="paired.state !== 'working'"
        />
        <BranchTag
          v-if="paired.state === 'working'"
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
      <Button link label="pair an agent" :pt="LINK_PT" @click="emit('pair')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import type { PairedAgent } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'
import BranchTag from '../../ui/BranchTag.vue'

// Rendered from the latest transaction's intent — never a fabricated status.
defineProps<{
  paired?: PairedAgent
  viewedBranch: string
}>()

const emit = defineEmits<{
  pair: []
}>()

const LINK_PT = { root: { class: 'p-0 text-base font-normal' } }
</script>
