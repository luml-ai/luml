<template>
  <div :title="fullLine" class="flex min-w-0 items-center gap-2 text-sm text-muted-color">
    <ActorChip
      :actor="provenance.lastEditedBy"
      :uncertain="provenance.attributionUncertain"
      muted
    />
    <span class="truncate">· {{ provenance.intent }}</span>
    <span
      v-if="repairedAttempts"
      class="inline-flex shrink-0 items-center gap-1"
      :aria-label="repairedLine"
    >
      <History :size="14" />
      {{ repairedAttempts }} failed
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { History } from 'lucide-vue-next'
import { formatCount } from '../../model/format'
import type { ProvenanceInfo } from '../../model/types'
import ActorChip from '../../ui/ActorChip.vue'

/**
 * Who last touched this version and why — a signature, not a sentence. Creation
 * authorship, the step number and the shape of the folded repair history are
 * recall rather than a glance, so they ride in the hover title.
 */
const props = defineProps<{
  provenance: ProvenanceInfo
  repairedAttempts?: number
}>()

// Counted, not numbered. How many runs of this cell failed before the one
// standing now is a fact the session watched go by; which version each of them
// was is not, and pairing them up would put invented numbers on screen.
const repairedLine = computed(() => {
  const attempts = props.repairedAttempts
  return attempts ? `${formatCount(attempts, 'failed attempt')} folded in` : ''
})

const fullLine = computed(() => {
  const { createdBy, lastEditedBy, step } = props.provenance
  const parts = [`created ${createdBy.label}`, `last edit ${lastEditedBy.label}`, `step ${step}`]
  if (repairedLine.value) parts.push(repairedLine.value)
  return parts.join(' · ')
})
</script>
