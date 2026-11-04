<template>
  <div class="flex items-center gap-2 text-sm">
    <Paperclip :size="14" class="text-muted-color shrink-0" />
    <span class="font-medium">{{ block.name }}</span>
    <span class="text-muted-color">{{ formattedSize }}</span>
  </div>
</template>

<script setup lang="ts">
import type { CellFileBlockProps } from './preview.interface'
import { computed } from 'vue'
import { Paperclip } from 'lucide-vue-next'
import { getSizeText } from '@/helpers/string'

const props = defineProps<CellFileBlockProps>()

const formattedSize = computed(() => getSizeText(props.block.size))
</script>

<style scoped></style>
