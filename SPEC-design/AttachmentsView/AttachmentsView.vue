<template>
  <CurrentAttachmentsView v-bind="$props" />
</template>

<script setup lang="ts">
// UIP-002: the page is unchanged; only the table preview now also takes `.parquet` files.
import type { AttachmentNode } from '@/blocks/ModelAttachments/FileNode.vue'
import CurrentAttachmentsView from '@/pages/experiments-evals-attachments/AttachmentsView/AttachmentsView.vue'

type Props = {
  breadcrumbs: { label: string; route: string }[]
  tree: AttachmentNode[]
  selected?: { name: string; path: string; size?: string }
  table?: { headers: string[]; rows: Record<string, string>[]; rowsCount: number }
}

defineProps<Props>()
</script>
