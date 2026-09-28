<template>
  <section class="flex flex-col gap-3 min-w-0">
    <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 min-w-0">
      <h4 class="text-base font-medium">{{ title }}</h4>
      <InfoNote v-if="caption" label="" :subject="title">{{ caption }}</InfoNote>
    </div>
    <div
      class="rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 overflow-x-auto"
      :class="[padded === false ? 'p-0!' : '', grow ? 'flex-1' : '']"
    >
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
import InfoNote from '../ui/InfoNote.vue'

/**
 * Uniform exhibit frame. The specimen is the exhibit; the reasoning behind it
 * is a paragraph a reader asks for, so it sits behind the note toggle rather
 * than between every specimen and the next one.
 */
defineProps<{
  title: string
  caption?: string
  padded?: boolean
  grow?: boolean
}>()
</script>
