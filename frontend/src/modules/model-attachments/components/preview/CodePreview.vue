<template>
  <div class="content-code">
    <div v-if="isMarkdown" class="markdown-body" v-html="markdownText"></div>
    <pre v-else><code>{{ props.textContent }}</code></pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import 'github-markdown-css/github-markdown.css'

import type { CodePreviewProps } from '../../interfaces/interfaces'

const props = defineProps<CodePreviewProps>()

const isMarkdown = computed(() => {
  return props.fileName?.toLowerCase().endsWith('.md')
})
const markdownText = computed(() => {
  if (!isMarkdown.value) return ''
  const result = marked.parse(props.textContent)
  return DOMPurify.sanitize(result as string)
})
</script>

<style scoped>
.content-code {
  flex: 1;
  overflow: auto;
  line-height: 1.5;
  background: var(--surface-50);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  color: var(--p-text-color);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
}

.content-code pre {
  margin: 0;
}

.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
}

.markdown-body :deep(tr) {
  background-color: transparent !important;
}

.markdown-body :deep(th:empty) {
  display: none !important;
}
</style>
