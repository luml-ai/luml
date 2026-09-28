<template>
  <div class="flex flex-col">
    <div
      v-for="link in links"
      :key="`${link.branch}.${link.tracker.id}`"
      class="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-surface-200 py-3 first:border-t-0 first:pt-0 last:pb-0 dark:border-surface-700"
    >
      <KindBadge kind="experiment" icon-only />
      <span class="font-mono text-sm text-muted-color">{{ link.branch }}</span>
      <RouterLink v-if="link.tracker.url" class="link text-base" :to="link.tracker.url">
        {{ link.slug }}.{{ link.output }}
      </RouterLink>
      <span v-else class="font-mono text-base">{{ link.slug }}.{{ link.output }}</span>
      <TrackerStateBadge v-if="!link.tracker.url" :state="link.tracker.state" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { CompareTrackerLink } from '../../model/types'
import KindBadge from '../../ui/KindBadge.vue'
import TrackerStateBadge from '../../ui/TrackerStateBadge.vue'

defineProps<{ links: CompareTrackerLink[] }>()
</script>
