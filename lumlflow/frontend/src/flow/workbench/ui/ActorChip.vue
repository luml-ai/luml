<template>
  <span
    class="inline-flex min-w-0 items-center gap-1.5 text-base"
    :class="muted ? 'text-muted-color' : ''"
  >
    <component :is="actor.kind === 'agent' ? Bot : UserRound" :size="14" class="shrink-0" />
    <span class="truncate">{{ actor.label }}</span>
    <Tag
      v-if="uncertain"
      v-tooltip.top="'a mixed editing window. attribution is uncertain.'"
      severity="warn"
      :pt="UNCERTAIN_PT"
    >
      <TriangleAlert :size="14" class="shrink-0" />
      <span>uncertain</span>
    </Tag>
  </span>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { Bot, TriangleAlert, UserRound } from 'lucide-vue-next'
import type { ActorRef } from '../model/types'

defineProps<{
  actor: ActorRef
  /** Render the mixed-editing-window flag instead of a confident wrong name. */
  uncertain?: boolean
  muted?: boolean
}>()

const UNCERTAIN_PT = { root: { class: 'text-sm font-normal gap-1 px-1.5 py-0 shrink-0' } }
</script>
