<template>
  <SelectButton
    v-if="formattedLabel && !parseFailed"
    v-model="viewMode"
    :options="[formattedLabel, 'Raw']"
    :allow-empty="false"
    size="small"
    aria-label="Preview mode"
    class="view-toggle"
  />
  <div v-if="parseFailed" class="parse-status" role="status">Raw · Can't parse</div>
  <div class="content-code">
    <div v-if="viewMode === 'Rendered'" class="markdown-body" v-html="markdownText" />
    <HighlightedSource
      v-else-if="language || getFileType(fileName) === 'code'"
      :source="viewMode === 'Pretty' ? (prettyText ?? textContent) : textContent"
      :language="language"
      :file-name="fileName"
    />
    <pre v-else><code>{{ textContent }}</code></pre>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { SelectButton } from 'primevue'
import 'github-markdown-css/github-markdown.css'

import type { CodePreviewProps } from '../../interfaces/interfaces'
import { getFileType, getPreviewLanguage } from '../../utils/fileTypes'
import { prettySource } from '../../utils/prettySource'
import { renderMarkdown } from '../../utils/renderMarkdown'
import HighlightedSource from './HighlightedSource.vue'

const props = defineProps<CodePreviewProps>()
const language = computed(() => getPreviewLanguage(props.fileName))
const formattedLabel = computed(() => {
  if (language.value === 'markdown') return 'Rendered'
  if (language.value === 'json' || language.value === 'yaml') return 'Pretty'
  return undefined
})
const prettyText = computed(() => {
  if (language.value !== 'json' && language.value !== 'yaml') return undefined
  try {
    return prettySource(props.textContent, language.value)
  } catch {
    return undefined
  }
})
const parseFailed = computed(
  () => formattedLabel.value === 'Pretty' && prettyText.value === undefined,
)
const rawSelected = ref(false)
watch(
  () => props.fileName,
  () => {
    rawSelected.value = false
  },
)
const viewMode = computed({
  get: () => (rawSelected.value || parseFailed.value ? 'Raw' : (formattedLabel.value ?? 'Raw')),
  set: (value) => {
    rawSelected.value = value === 'Raw'
  },
})
const markdownText = computed(() => renderMarkdown(props.textContent))
</script>

<style scoped>
.view-toggle,
.parse-status {
  align-self: flex-start;
  margin-bottom: 0.5rem;
}

.parse-status {
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.content-code {
  flex: 1;
  min-height: 0;
  overflow: auto;
  line-height: 1.5;
  font-size: 14px;
  color: var(--p-text-color);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
}

.content-code pre {
  margin: 0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
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
