<template>
  <Dialog
    v-model:visible="visible"
    :header="title"
    :draggable="false"
    :pt="dialogPt"
    modal
    dismissable-mask
  >
    <div class="toolbar">
      <span class="size">{{ sizeLabel }}</span>
      <Select
        v-model="contentType"
        :options="contentTypes"
        option-label="label"
        option-value="value"
        option-disabled="disabled"
        size="small"
        class="select"
      ></Select>
      <Button severity="secondary" variant="outlined" size="small" :disabled="copied" @click="copy">
        <span>Copy</span>
        <component :is="copied ? CopyCheck : Copy" :size="14"></component>
      </Button>
      <Button severity="secondary" variant="outlined" size="small" @click="download">
        <span>Download</span>
        <Download :size="14"></Download>
      </Button>
    </div>
    <div class="body">
      <div v-if="contentType === ContentTypeEnum.yaml" class="formatted yaml-body">
        <pre>{{ yamlText }}</pre>
      </div>
      <div
        v-else-if="contentType === ContentTypeEnum.markdown"
        v-html="markdownText"
        class="formatted markdown-body"
      ></div>
      <VirtualScroller v-else :items="lines" :item-size="LINE_HEIGHT" class="lines">
        <template #item="{ item }">
          <div class="line">{{ item }}</div>
        </template>
      </VirtualScroller>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import 'github-markdown-css/github-markdown.css'
import type { DialogPassThroughOptions } from 'primevue'
import { computed, ref } from 'vue'
import { Button, Dialog, Select, VirtualScroller } from 'primevue'
import { Copy, CopyCheck, Download } from 'lucide-vue-next'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { isYamlLike, jsonToYaml, tryParseJson } from '../../helpers/texts'
import { downloadFileFromBlob } from '../../helpers/files'
import { FORMATTED_VIEW_MAX_BYTES, formatBytes, valueFileName } from './largeValue'
import { registerNestedViewer } from './nestedViewer'

type Props = {
  title: string
  value: unknown
  /** The value as text, as the preview shows it. */
  text: string
  /** UTF-8 size of `text`. */
  bytes: number
}

enum ContentTypeEnum {
  yaml = 'yaml',
  markdown = 'markdown',
  raw = 'raw',
}

const LINE_HEIGHT = 20
// Long lines are cut into rows of this length so every row has the same height.
const LINE_CHUNK = 1_000

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')

registerNestedViewer()

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'width: min(1200px, calc(100vw - 80px)); height: calc(100vh - 120px); max-height: none;',
  },
  content: {
    style: 'display: flex; flex-direction: column; flex: 1 1 auto; overflow: hidden;',
  },
}

const contentType = ref<ContentTypeEnum>(ContentTypeEnum.raw)
const copied = ref(false)

const formattedAllowed = computed(() => props.bytes < FORMATTED_VIEW_MAX_BYTES)

const sizeLabel = computed(() => formatBytes(props.bytes))

const contentTypes = computed(() => [
  {
    label: 'YAML',
    value: ContentTypeEnum.yaml,
    disabled: !formattedAllowed.value || !isYamlLike(JSON.stringify(props.value)),
  },
  {
    label: 'Markdown',
    value: ContentTypeEnum.markdown,
    disabled: !formattedAllowed.value,
  },
  {
    label: 'Raw',
    value: ContentTypeEnum.raw,
  },
])

const lines = computed(() => {
  const rows: string[] = []
  for (const line of props.text.split('\n')) {
    if (line.length <= LINE_CHUNK) {
      rows.push(line)
      continue
    }
    for (let start = 0; start < line.length; start += LINE_CHUNK) {
      rows.push(line.slice(start, start + LINE_CHUNK))
    }
  }
  return rows
})

const markdownText = computed(() => {
  return DOMPurify.sanitize(marked.parse(props.text, { async: false }))
})

const yamlText = computed(() => {
  const value =
    typeof props.value === 'string' ? (tryParseJson(props.value) ?? props.value) : props.value
  return jsonToYaml(value)
})

function copy() {
  navigator.clipboard.writeText(props.text)
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 1000)
}

function download() {
  const blob = new Blob([props.text], { type: 'text/plain;charset=utf-8' })
  downloadFileFromBlob(blob, valueFileName(props.title, props.value))
}
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex: 0 0 auto;
}

.size {
  margin-right: auto;
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.select {
  width: 120px;
}

.body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  font-size: 14px;
}

.lines {
  position: absolute;
  inset: 0;
}

.line {
  height: 20px;
  line-height: 20px;
  padding: 0 12px;
  white-space: pre;
  font-family: monospace;
  font-size: 12px;
}

.formatted {
  position: absolute;
  inset: 0;
  overflow: auto;
  padding: 12px;
}

.yaml-body pre {
  margin: 0;
  white-space: pre;
}

.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
}
</style>
