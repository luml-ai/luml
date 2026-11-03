<template>
  <div v-html="html" class="markdown-body"></div>
</template>

<script setup lang="ts">
import type { CellMarkdownBlockProps } from './preview.interface'
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import 'github-markdown-css/github-markdown.css'

const props = defineProps<CellMarkdownBlockProps>()

const html = computed(() => DOMPurify.sanitize(marked.parse(props.block.text) as string))
</script>

<style scoped>
.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
}
/* Tailwind's reset drops list markers and github-markdown-css does not bring
   them back, so numbered and bulleted lists read as plain lines. */
.markdown-body :deep(ol) {
  list-style-type: decimal;
}
.markdown-body :deep(ul) {
  list-style-type: disc;
}
.markdown-body :deep(ul ul) {
  list-style-type: circle;
}
</style>
