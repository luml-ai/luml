<template>
  <Message severity="secondary" size="small" :pt="NOTICE_PT">
    <template #icon><Lock :size="14" class="shrink-0" /></template>
    <span class="min-w-0 text-sm">
      <code class="font-mono">{{ holder }}</code> holds the files. use, rewind and adopt wait.
    </span>
    <Button
      v-tooltip.top="'take the files anyway. the agent loses its file view.'"
      link
      severity="danger"
      label="force"
      :pt="LINK_PT"
      @click="emit('force')"
    />
  </Message>
</template>

<script setup lang="ts">
import { Button, Message } from 'primevue'
import { Lock } from 'lucide-vue-next'

withDefaults(defineProps<{ holder?: string }>(), { holder: 'an agent' })

const emit = defineEmits<{ force: [] }>()

const NOTICE_PT = { content: { class: 'gap-2 py-1' } }
const LINK_PT = { root: { class: 'p-0 text-sm font-normal' } }
</script>
