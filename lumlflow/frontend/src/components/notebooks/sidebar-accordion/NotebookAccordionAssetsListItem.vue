<template>
  <div class="flex items-center gap-1 text-sm text-muted-color overflow-hidden">
    <component v-if="showIcon && icon" :is="icon" :size="12" class="shrink-0" />
    <span class="truncate overflow-hidden">{{ item.name }}</span>
    <span v-if="item.unmaterialized" class="text-xs text-(--p-badge-warn-background) shrink-0">
      unmaterialized
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NotebookAssetInterface } from '@/components/notebooks/notebooks.interface'
import { NOTEBOOK_ASSET_ICONS } from '@/components/notebooks/notebooks.const'

interface Props {
  item: NotebookAssetInterface
  showIcon?: boolean
}

const props = defineProps<Props>()

const icon = computed(() => {
  return NOTEBOOK_ASSET_ICONS[props.item.type]
})
</script>

<style scoped></style>
