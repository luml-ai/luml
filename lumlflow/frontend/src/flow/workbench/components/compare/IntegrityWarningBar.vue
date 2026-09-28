<template>
  <Message severity="warn" size="small">
    <template #icon><TriangleAlert :size="15" class="shrink-0" /></template>
    <div class="flex min-w-0 flex-col gap-1">
      <p class="text-base">
        <span class="font-medium">{{ kindLabel }}</span>
        <span> · </span>
        <span v-html="messageHtml" />
      </p>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span class="text-sm">affects</span>
        <BranchTag v-for="branch in warning.affectedBranches" :key="branch" :name="branch" />
      </div>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Message } from 'primevue'
import { TriangleAlert } from 'lucide-vue-next'
import type { CompareWarning } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'

/**
 * Comparability is checked before the numbers are read: where pin-at-fork
 * stopped holding, the warning says so above the columns. Why that matters is
 * the reader's own judgement and does not need narrating underneath.
 */
const props = defineProps<{ warning: CompareWarning }>()

const KIND_LABELS: Record<CompareWarning['kind'], string> = {
  'divergent-pin': 'divergent pin',
  'dataset-mismatch': 'dataset mismatch',
  'scoring-mismatch': 'scoring mismatch',
  'nondeterministic-input': 'nondeterministic input',
}

const kindLabel = computed(() => KIND_LABELS[props.warning.kind])

/** Render `slug` spans in the message as code without a markdown pass. */
const messageHtml = computed(() =>
  props.warning.message
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-sm">$1</code>'),
)
</script>
