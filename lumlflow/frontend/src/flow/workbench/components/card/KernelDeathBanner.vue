<template>
  <Message severity="error" size="small">
    <template #icon><ZapOff :size="15" class="shrink-0" /></template>
    <div class="flex w-full flex-wrap items-center gap-x-3 gap-y-1">
      <p class="min-w-0 flex-1 text-base">
        <span class="font-medium">the kernel died · {{ cause ?? 'out of memory' }}</span>
        <span v-html="detailHtml" />
      </p>
      <Button text label="restart kernel" @click="emit('restart-kernel')">
        <template #icon><RefreshCw :size="14" /></template>
      </Button>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button, Message } from 'primevue'
import { RefreshCw, ZapOff } from 'lucide-vue-next'
import { inlineCodeHtml } from './inlineCode'

/**
 * Kernel death is observable (exit status / OOM kill) and recoverable: the
 * kernel is stateless relative to the store, so the banner can honestly say
 * nothing recorded is lost.
 */
const props = defineProps<{
  /** The cell that was materializing when the kernel died. */
  slug: string
  cause?: string
}>()

const emit = defineEmits<{ 'restart-kernel': [] }>()

const detailHtml = computed(() =>
  inlineCodeHtml(
    `. \`${props.slug}\` was materializing. nothing recorded is lost. the queue is drained.`,
  ),
)
</script>
