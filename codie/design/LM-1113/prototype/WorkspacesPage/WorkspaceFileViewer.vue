<template>
  <LumlflowCard class="viewer" :class="{ 'viewer-agent': agent }" :style="agent ? { '--agent-color': agent.color } : undefined">
    <div class="viewer-inner">
      <div class="preview-header">
        <div class="file-info-wrapper">
          <div class="file-info">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-meta">{{ file.size }} · Modified {{ file.modified }}</span>
          </div>
          <div class="file-path-row">
            <span class="file-path">{{ file.path }}</span>
            <Button class="icon-wrapper" variant="text" severity="secondary" aria-label="Copy path">
              <template #icon>
                <Copy class="icon-btn" />
              </template>
            </Button>
          </div>
        </div>
        <Button class="icon-wrapper" variant="text" severity="secondary" aria-label="Close preview">
          <template #icon>
            <X class="icon-btn" />
          </template>
        </Button>
      </div>

      <!-- product:PROP-004 B-15: a file an agent is changing, shown like a cell an agent works on. -->
      <div
        v-if="agent"
        class="live-strip"
        role="status"
        title="Read-only until 3 minutes after the agent's last change to this file."
      >
        <Lock :size="14" class="no-shrink" />
        <span class="truncate">{{ agent.label }} is working on this file</span>
      </div>

      <div class="preview-body" :class="{ 'live-body': agent }">
        <LumlPackagePreview v-if="luml" :luml="luml" />

        <div v-else-if="previewState" class="preview-state">
          <span>{{ STATE_TEXT[previewState] }}</span>
        </div>

        <div v-else-if="table" class="table-preview">
          <AttachmentsPreviewDataTable
            :value="table.rows"
            :paginator="true"
            :rows="10"
            :rows-per-page-options="[10, 20, 50]"
            :total-records="table.rowsCount"
            size="small"
          >
            <Column v-for="column in table.headers" :key="column" :field="column" :header="column"></Column>
          </AttachmentsPreviewDataTable>
        </div>

        <div v-else-if="image" class="content-image">
          <img :src="image" :alt="file.name" />
        </div>

        <div v-else-if="svg" class="content-image content-svg">
          <!-- eslint-disable-next-line vue/no-v-html -- sample SVG from the story, not user input -->
          <div class="svg-container" v-html="svg"></div>
        </div>

        <div v-else-if="media" class="content-media" :class="`content-${media}`">
          <!-- No source in the design: the browser shows the player's controls (B-02). -->
          <audio v-if="media === 'audio'" controls></audio>
          <video v-else controls></video>
        </div>

        <div v-else-if="pdf" class="content-frame content-pdf">
          <!-- The app loads the file in an iframe; the design draws the page. -->
          <div class="pdf-page">
            <div class="pdf-line pdf-title"></div>
            <div v-for="i in 8" :key="i" class="pdf-line" :style="{ width: `${92 - (i % 3) * 14}%` }"></div>
            <div class="pdf-figure"></div>
            <div v-for="i in 4" :key="`b${i}`" class="pdf-line" :style="{ width: `${88 - (i % 2) * 20}%` }"></div>
          </div>
        </div>

        <div v-else-if="html !== undefined" class="content-frame content-html">
          <iframe :srcdoc="html" sandbox="" :title="file.name"></iframe>
        </div>

        <template v-else-if="textContent !== undefined">
          <!-- B-13: rendered / raw for Markdown, pretty / raw for JSON and YAML. B-15: Edit, as NotebookCode. -->
          <div class="view-toggle">
            <SelectButton
              v-if="viewOptions && !editing"
              :model-value="viewLabel"
              :options="viewOptions"
              :allow-empty="false"
              size="small"
            />
            <span v-else></span>
            <div class="edit-actions">
              <template v-if="editing">
                <Button text severity="secondary" label="Cancel" size="small" />
                <Button label="Save" size="small" />
              </template>
              <Button v-else text severity="secondary" label="Edit" size="small" :disabled="!!agent">
                <template #icon>
                  <Pencil :size="14" />
                </template>
              </Button>
            </div>
          </div>

          <Message v-if="conflict" severity="warn" size="small" class="conflict">
            This file changed on disk after you started to edit it.
            <div class="conflict-actions">
              <Button label="Overwrite" size="small" />
              <Button text severity="secondary" label="Reload" size="small" />
            </div>
          </Message>

          <UiCodeEditor
            v-if="editing"
            :model-value="textContent"
            :aria-label="`contents of ${file.name}`"
            max-height="none"
            class="editor"
          />
          <div v-else class="content-code">
            <!-- eslint-disable-next-line vue/no-v-html -- sample Markdown from the story, not user input -->
            <div v-if="isMarkdown && view !== 'raw'" class="markdown-body" v-html="markdownHtml"></div>
            <!-- eslint-disable-next-line vue/no-v-html -- highlight.ts escapes the text first -->
            <pre v-else><code v-html="codeHtml"></code></pre>
          </div>
        </template>
      </div>
    </div>
  </LumlflowCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import { Copy, Lock, Pencil, X } from 'lucide-vue-next'
import { Button, Column, Message, SelectButton } from '@/ui'
import LumlflowCard from '@/ui/LumlflowCard.vue'
import UiCodeEditor from '@/components/UiCodeEditor/UiCodeEditor.vue'
import AttachmentsPreviewDataTable from '@/ui/AttachmentsPreviewDataTable.vue'
import LumlPackagePreview, { type LumlPackage } from './LumlPackagePreview.vue'
import { highlight, languageOf } from './highlight'

export type ViewerFile = { name: string; path: string; size: string; modified: string }
export type ViewerState = 'unsupported' | 'empty' | 'too-big'
/** B-13: `rendered` / `raw` for Markdown, `pretty` / `raw` for JSON and YAML. */
export type ViewerView = 'rendered' | 'pretty' | 'raw'
export type ViewerTable = { headers: string[]; rows: Record<string, string>[]; rowsCount: number }

type Props = {
  file: ViewerFile
  textContent?: string
  /** B-13: for JSON, the pretty-printed text; `textContent` stays the raw file. */
  prettyContent?: string
  view?: ViewerView
  table?: ViewerTable
  /** B-02: the other attachment previews. `image`: a URL; `svg`: the markup; `html`: the document. */
  image?: string
  svg?: string
  media?: 'audio' | 'video'
  pdf?: boolean
  html?: string
  previewState?: ViewerState
  /** product:PROP-004 B-09 – B-11: a `.luml` package (read from its manifest.json). */
  luml?: LumlPackage
  /** B-15: the text file is being edited; `conflict`: it changed on disk meanwhile. */
  editing?: boolean
  conflict?: boolean
  /** B-15: an agent changed the file during its session; the file is read-only for the person. */
  agent?: { label: string; color: string }
}

const props = defineProps<Props>()

// product:PROP-004 B-05: a file it can't preview shows name, size and date (the header) only.
const STATE_TEXT: Record<ViewerState, string> = {
  unsupported: 'No preview for this file type',
  empty: 'File is empty',
  'too-big': 'File is too large for preview',
}

const language = computed(() => languageOf(props.file.name))
const isMarkdown = computed(() => props.file.name.toLowerCase().endsWith('.md'))

const viewOptions = computed(() => {
  if (isMarkdown.value) return ['Rendered', 'Raw']
  if (language.value === 'json' || language.value === 'yaml') return ['Pretty', 'Raw']
  return null
})
const view = computed<ViewerView>(() => props.view ?? (isMarkdown.value ? 'rendered' : 'pretty'))
const viewLabel = computed(() => (view.value === 'raw' ? 'Raw' : isMarkdown.value ? 'Rendered' : 'Pretty'))

const markdownHtml = computed(() => (isMarkdown.value ? (marked.parse(props.textContent ?? '') as string) : ''))

// B-12: code is highlighted; the raw view of a JSON / YAML / Markdown file is the plain text.
const codeHtml = computed(() => {
  const text = props.textContent ?? ''
  if (view.value === 'raw' && viewOptions.value) return highlight(text, 'plain')
  if (language.value === 'json') return highlight(props.prettyContent ?? text, 'json')
  return highlight(text, language.value)
})
</script>

<style scoped>
.viewer {
  min-width: 0;
}

.viewer-inner {
  display: flex;
  flex-direction: column;
  height: 640px;
}

/* From @luml/attachments FilePreviewHeader.vue, plus the date and a close button. */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 0 0 1rem;
}

.file-info-wrapper {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.file-info {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.file-name {
  font-weight: 500;
}

.file-meta,
.file-path {
  color: var(--p-form-field-float-label-color);
  font-size: 0.875rem;
}

.file-path-row {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 6px;
}

.file-path {
  word-break: break-all;
}

.icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  width: auto;
  flex-shrink: 0;
}

.icon-btn {
  width: 18px;
  height: 18px;
  color: var(--p-form-field-float-label-color);
}

.preview-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.table-preview {
  overflow: auto;
  flex: 1;
}

.view-toggle {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.conflict {
  flex: none;
  margin-bottom: 0.5rem;
}

.conflict-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.editor {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

/* B-15, as blocks/NotebookCell: border and strip in the agent's colour, body dimmed. */
.viewer-agent {
  border-color: var(--agent-color);
}

.live-strip {
  flex: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  color: var(--agent-color);
  background: color-mix(in srgb, var(--agent-color) 12%, transparent);
}

.live-body {
  opacity: 0.6;
}

.no-shrink {
  flex-shrink: 0;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-code {
  flex: 1;
  overflow: auto;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  color: var(--p-text-color);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  /* B-12: token colours, defined here (see highlight.ts). */
  --hl-comment: #6b7280;
  --hl-string: #15803d;
  --hl-keyword: #7c3aed;
  --hl-number: #b45309;
  --hl-key: #1d4ed8;
}

.content-code pre {
  margin: 0;
}

.content-code :deep(.hl-comment) {
  color: var(--hl-comment);
  font-style: italic;
}

.content-code :deep(.hl-string) {
  color: var(--hl-string);
}

.content-code :deep(.hl-keyword) {
  color: var(--hl-keyword);
}

.content-code :deep(.hl-number) {
  color: var(--hl-number);
}

.content-code :deep(.hl-key) {
  color: var(--hl-key);
}

.markdown-body {
  white-space: normal;
  color: var(--p-text-color);
}

/* From @luml/attachments ImagePreview.vue / SvgPreview.vue. */
.content-image {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  overflow: auto;
}

.content-image img,
.svg-container :deep(svg) {
  max-width: 100%;
  max-height: 100%;
  height: auto;
}

/* From @luml/attachments MediaPreview.vue. */
.content-media {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
}

.content-media audio {
  width: 100%;
  max-width: 480px;
}

.content-media video {
  width: 100%;
  max-height: 100%;
  background: #000;
  border-radius: 4px;
}

/* From @luml/attachments PdfPreview.vue / HtmlPreview.vue: an iframe filling the body. */
.content-frame {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  overflow: hidden;
}

.content-frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

.content-pdf {
  display: flex;
  justify-content: center;
  overflow: auto;
  padding: 16px;
  background-color: var(--p-surface-100, #f3f4f6);
}

.pdf-page {
  width: 420px;
  min-height: 560px;
  padding: 40px 36px;
  background: #fff;
  box-shadow: 0 1px 4px rgb(0 0 0 / 15%);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pdf-line {
  height: 8px;
  border-radius: 4px;
  background: #e5e7eb;
}

.pdf-title {
  height: 14px;
  width: 60%;
  margin-bottom: 8px;
  background: #d1d5db;
}

.pdf-figure {
  height: 120px;
  margin: 8px 0;
  border-radius: 6px;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.preview-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px dashed var(--p-content-border-color);
  color: var(--p-text-muted-color);
}
</style>
