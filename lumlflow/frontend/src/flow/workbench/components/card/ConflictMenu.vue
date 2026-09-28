<template>
  <Message severity="warn" size="small">
    <template #icon><TriangleAlert :size="14" class="shrink-0" /></template>
    <div class="flex w-full flex-wrap items-center gap-x-3 gap-y-1">
      <span class="min-w-40 flex-1 text-base">your edit is based on an older version</span>
      <div class="flex shrink-0 items-center gap-2">
        <Button severity="warn" label="save to a new lane" @click="emit('resolve', 'fork')">
          <template #icon><Split :size="14" /></template>
        </Button>
        <Button text severity="secondary" label="overwrite" @click="emit('resolve', 'overwrite')" />
      </div>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { Button, Message } from 'primevue'
// Never a git glyph: a fork icon says the word the copy stopped saying.
import { Split, TriangleAlert } from 'lucide-vue-next'

// Saving to a new lane is the promoted resolution: overwriting loses
// someone else's version, saving to a new lane loses nothing.
const emit = defineEmits<{ resolve: [choice: 'overwrite' | 'fork'] }>()
</script>
