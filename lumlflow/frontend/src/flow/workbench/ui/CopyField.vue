<template>
  <div
    class="flex items-center gap-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 px-3 py-2"
  >
    <code class="font-mono text-base flex-1 truncate select-all">{{ value }}</code>
    <Button
      v-tooltip.top="copied ? 'Copied' : 'Copy'"
      text
      rounded
      severity="secondary"
      size="small"
      :aria-label="`Copy ${value}`"
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

const props = defineProps<{ value: string }>()

const { copied, copy } = useCopy(() => props.value)
</script>
