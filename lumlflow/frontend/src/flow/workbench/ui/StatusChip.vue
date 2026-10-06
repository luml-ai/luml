<template>
  <span class="inline-flex items-center gap-1.5 min-w-0">
    <Tag :severity="severity" :pt="tagPt" :class="subdued ? 'opacity-60' : ''">
      <span class="inline-flex items-center gap-1">
        <span
          v-if="status === 'running' || status === 'refreshing'"
          class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"
        />
        {{ label }}
      </span>
    </Tag>
    <span v-if="cause" class="text-sm text-muted-color truncate" v-html="causeHtml" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { CellStatus, StaleInfo } from '../model/types'

const props = defineProps<{
  status: CellStatus
  stale?: StaleInfo
  compact?: boolean
}>()

const tagPt = { root: { class: 'text-sm font-normal px-2 py-0.5' } }

const label = computed(() => {
  if (props.status === 'stale' && props.stale?.transitive && !props.compact) {
    return 'stale · downstream'
  }
  return props.status
})

const severity = computed(() => {
  switch (props.status) {
    case 'materialized':
      return 'success'
    case 'running':
    case 'refreshing':
      return 'info'
    case 'stale':
      return 'warn'
    case 'failed':
      return 'danger'
    default:
      return 'secondary'
  }
})

const subdued = computed(
  () => props.status === 'unmaterialized' || (props.status === 'stale' && props.stale?.transitive),
)

const cause = computed(() => (!props.compact && props.status === 'stale' ? props.stale?.cause : ''))

const causeHtml = computed(() =>
  (cause.value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-sm">$1</code>'),
)
</script>
