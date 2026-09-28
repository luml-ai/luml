<template>
  <div
    class="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border border-surface-200 bg-surface-0 p-5 dark:border-surface-700 dark:bg-surface-900"
  >
    <div class="flex flex-col">
      <Button @click="emit('adopt')">
        <Replace :size="14" />
        <span>
          Adopt <span class="font-mono">{{ asset }}</span> from
          <span class="font-mono">{{ winner }}</span> onto
          <span class="font-mono">{{ target }}</span>
        </span>
      </Button>
    </div>

    <div class="flex flex-col">
      <Button severity="secondary" outlined @click="emit('export')">
        <FileDown :size="14" />
        <span>Export the chosen slice</span>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { FileDown, Replace } from 'lucide-vue-next'

defineProps<{
  winner: string
  asset: string
  target: string
}>()

const emit = defineEmits<{
  adopt: []
  export: []
}>()
</script>
