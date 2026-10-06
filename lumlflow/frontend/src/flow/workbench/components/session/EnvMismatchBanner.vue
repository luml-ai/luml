<template>
  <Message severity="warn" size="small">
    <template #icon><PackageX :size="15" class="shrink-0" /></template>
    <div class="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5">
      <p class="min-w-0 flex-1 text-base">
        <span class="font-medium">restart kernel to apply.</span>
        it imported {{ named }} before the env changed.
      </p>
      <Button label="Restart kernel" severity="warn" text @click="emit('restart')">
        <template #icon><RotateCcw :size="14" /></template>
      </Button>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button, Message } from 'primevue'
import { PackageX, RotateCcw } from 'lucide-vue-next'
import { formatCount } from '../../model/format'

const props = defineProps<{
  behind?: string[]
}>()

const emit = defineEmits<{ restart: [] }>()

const named = computed(() => {
  const behind = props.behind ?? []
  if (behind.length === 0) return 'packages'
  if (behind.length <= 2) return behind.join(' and ')
  return `${behind[0]}, ${behind[1]} and ${formatCount(behind.length - 2, 'other')}`
})
</script>
