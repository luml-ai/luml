<template>
  <Message severity="info" size="small" :pt="MARKER_PT">
    <template #icon><History :size="14" class="shrink-0" /></template>
    <span class="text-base">{{ formatCount(count, 'change') }} since you were here</span>
    <Button link label="open at cursor" :pt="LINK_PT" @click="emit('open')" />
  </Message>
</template>

<script setup lang="ts">
import { Button, Message } from 'primevue'
import { History } from 'lucide-vue-next'
import { formatCount } from '../../model/format'

// A marker, not an inbox: it names the gap and offers the one gesture that
// closes it.
defineProps<{ count: number }>()

const emit = defineEmits<{ open: [] }>()

const MARKER_PT = { content: { class: 'gap-2 py-1' } }
const LINK_PT = { root: { class: 'p-0 text-base font-normal' } }
</script>
