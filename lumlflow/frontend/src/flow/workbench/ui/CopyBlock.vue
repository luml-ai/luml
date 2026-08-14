<template>
  <div
    class="relative rounded-lg border border-surface-200 bg-surface-50 dark:border-surface-700 dark:bg-surface-800"
  >
    <pre
      class="max-h-96 select-all overflow-auto whitespace-pre-wrap p-3 pr-10 font-mono text-sm leading-relaxed"
      >{{ value }}</pre
    >
    <Button
      v-tooltip.top="copied ? 'Copied' : 'Copy'"
      class="absolute! right-1 top-1"
      text
      rounded
      severity="secondary"
      size="small"
      :aria-label="label"
      @click="copy"
    >
      <template #icon>
        <Check v-if="copied" :size="14" class="text-(--p-message-success-color)" />
        <Copy v-else :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Check, Copy } from 'lucide-vue-next'
import { useCopy } from './useCopy'

/**
 * Something handed over whole: a handoff payload, a connect prompt. The reader
 * checks it and copies all of it, so the block is the preview and the copy at
 * once — `CopyField` is the one-line sibling, and truncating a block would hide
 * most of what the button is about to carry.
 *
 * The copy sits in the corner with `absolute!`: `.p-button` sets `position:
 * relative` and wins the cascade over the utility, which lands the button at
 * its static position — under the block, outside the border, where it reads as
 * an icon belonging to nothing.
 */
const props = withDefaults(defineProps<{ value: string; label?: string }>(), { label: 'Copy' })

const { copied, copy } = useCopy(() => props.value)
</script>
