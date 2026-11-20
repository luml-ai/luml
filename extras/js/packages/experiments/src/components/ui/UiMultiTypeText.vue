<template>
  <div class="item">
    <header class="header">
      <h4 class="title">{{ title }}</h4>
      <div class="right">
        <Select
          v-if="!isLarge"
          v-model="contentType"
          :options="contentTypes"
          option-label="label"
          option-value="value"
          option-disabled="disabled"
          size="small"
          class="select"
        ></Select>
        <Button
          severity="secondary"
          variant="text"
          v-tooltip.left="'Copy'"
          :disabled="copied"
          @click="copy"
        >
          <template #icon>
            <component :is="copied ? CopyCheck : Copy" :size="14"></component>
          </template>
        </Button>
      </div>
    </header>
    <div v-if="isLarge" class="content">
      <div>{{ preview }}</div>
      <div class="large-footer">
        <span class="large-info">{{ sizeLine }}</span>
        <Button severity="secondary" variant="outlined" size="small" @click="viewerOpened = true">
          Show all
        </Button>
        <Button severity="secondary" variant="outlined" size="small" @click="download">
          <span>Download</span>
          <Download :size="14"></Download>
        </Button>
      </div>
      <JsonValueView
        v-if="viewerOpened"
        v-model:visible="viewerOpened"
        :title="title"
        :value="text"
        :text="displayText"
        :bytes="bytes"
      />
    </div>
    <div v-else class="content">
      <div v-if="contentType === ContentTypeEnum.yaml" class="yaml-body">
        <pre>{{ yamlText }}</pre>
      </div>
      <div
        v-else-if="contentType === ContentTypeEnum.markdown"
        v-html="markdownText"
        class="markdown-body"
      ></div>
      <div v-else>{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import 'github-markdown-css/github-markdown.css'
import { computed, inject, ref } from 'vue'
import { Select, Button } from 'primevue'
import { Copy, CopyCheck, Download } from 'lucide-vue-next'
import { marked } from 'marked'
import { isYamlLike, jsonToYaml, MarkdownRendererKey, tryParseJson } from '../../helpers/texts'
import DOMPurify from 'dompurify'
import { downloadFileFromBlob } from '../../helpers/files'
import {
  isLargeText,
  previewLine,
  previewText,
  utf8ByteLength,
  valueFileName,
  valueText,
} from './largeValue'
import JsonValueView from './JsonValueView.vue'

type Props = {
  title: string
  text: any
}

enum ContentTypeEnum {
  yaml = 'yaml',
  markdown = 'markdown',
  raw = 'raw',
}

const props = defineProps<Props>()

const contentType = ref<ContentTypeEnum>(ContentTypeEnum.raw)
const copied = ref(false)
const viewerOpened = ref(false)

// Large values show a preview only: no YAML check, Markdown or full render on the page.
const displayText = computed(() => valueText(props.text))
const isLarge = computed(() => isLargeText(displayText.value))
const preview = computed(() => previewText(displayText.value))
const bytes = computed(() => (isLarge.value ? utf8ByteLength(displayText.value) : 0))
const sizeLine = computed(() => previewLine(bytes.value))

const contentTypes = computed(() => [
  {
    label: 'YAML',
    value: ContentTypeEnum.yaml,
    disabled: !isYamlLike(JSON.stringify(props.text)),
  },
  {
    label: 'Markdown',
    value: ContentTypeEnum.markdown,
  },
  {
    label: 'Raw',
    value: ContentTypeEnum.raw,
  },
])

const renderMarkdown = inject(MarkdownRendererKey, (source: string) =>
  DOMPurify.sanitize(marked.parse(source, { async: false })),
)
const markdownText = computed(() =>
  renderMarkdown(typeof props.text === 'object' ? JSON.stringify(props.text) : String(props.text)),
)

const yamlText = computed(() => {
  const val = typeof props.text === 'string' ? (tryParseJson(props.text) ?? props.text) : props.text
  return jsonToYaml(val)
})

function copy() {
  navigator.clipboard.writeText(
    typeof props.text === 'object' ? JSON.stringify(props.text) : `${props.text}`,
  )
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 1000)
}

function download() {
  const blob = new Blob([displayText.value], { type: 'text/plain;charset=utf-8' })
  downloadFileFromBlob(blob, valueFileName(props.title, props.text))
}
</script>

<style scoped>
.item {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
}

.header {
  margin-bottom: 18px;
  padding-bottom: 4px;
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.title {
  font-size: 16px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.select {
  width: 120px;
}

.content {
  font-size: 14px;
  overflow-x: auto;
}

.yaml-body {
  margin: 0;
  white-space: pre;
  word-break: normal;
  overflow-wrap: normal;
}

.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
}

.large-footer {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.large-info {
  color: var(--p-text-muted-color);
  font-size: 12px;
  margin-right: auto;
}
</style>
