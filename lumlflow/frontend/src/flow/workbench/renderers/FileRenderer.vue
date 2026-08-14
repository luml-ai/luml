<template>
  <div class="flex items-center gap-3 py-1 min-w-0">
    <span
      class="rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-2.5 shrink-0"
    >
      <component :is="icon" :size="20" class="text-muted-color" />
    </span>
    <span class="min-w-0 flex-1">
      <span class="block font-mono text-base truncate">{{ preview.fileName }}</span>
      <span class="block text-sm text-muted-color">
        {{ formatBytes(preview.sizeBytes) }} · {{ preview.contentType }}
      </span>
    </span>
    <a class="link text-sm inline-flex items-center gap-1 shrink-0" href="#" @click.prevent>
      <Download :size="14" />
      download
    </a>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Download, File, FileArchive, FileImage, FileText, type LucideIcon } from 'lucide-vue-next'
import { formatBytes } from '../model/format'
import type { FilePreview } from '../model/types'
import type { RenderDensity } from './shared'

const props = defineProps<{
  preview: FilePreview
  density?: RenderDensity
}>()

const icon = computed<LucideIcon>(() => {
  const type = props.preview.contentType
  if (type.startsWith('image/')) return FileImage
  if (type.startsWith('text/')) return FileText
  if (type === 'application/octet-stream' || type.includes('zip') || type.includes('tar')) {
    return FileArchive
  }
  return File
})
</script>
