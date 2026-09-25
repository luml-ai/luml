<template>
  <Tag :value="label" :severity="severity" :pt="TAG_PT" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { TrackerExperimentState } from '@/flow/api/types'

const props = defineProps<{ state: TrackerExperimentState }>()

const TAG_PT = { root: { class: 'text-sm font-normal px-1.5 py-0 shrink-0' } }

const label = computed(() => {
  if (props.state === 'missing') return 'removed'
  return props.state
})

const severity = computed(() => {
  if (props.state === 'ok') return 'success'
  if (props.state === 'unreachable') return 'warn'
  return 'secondary'
})
</script>
