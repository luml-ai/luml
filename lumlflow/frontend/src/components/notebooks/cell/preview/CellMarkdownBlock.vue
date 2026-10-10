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
</style>
