<template>
  <div class="overflow-auto" :class="bodyMaxClass(density)">
    <!-- eslint-disable-next-line vue/no-v-html — sanitized through DOMPurify -->
    <div class="markdown-body" v-html="html" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import 'github-markdown-css/github-markdown.css'
import type { NotePreview } from '../model/types'
import { bodyMaxClass, type RenderDensity } from './shared'

const props = defineProps<{
  preview: NotePreview
  density?: RenderDensity
}>()

const html = computed(() => {
  const sanitized = DOMPurify.sanitize(marked.parse(props.preview.markdown) as string, {
    FORBID_TAGS: ['style', 'form', 'input', 'button'],
  })
  const template = document.createElement('template')
  template.innerHTML = sanitized
  for (const image of template.content.querySelectorAll('img')) {
    image.removeAttribute('srcset')
    if (isRemoteImage(image.getAttribute('src') ?? '')) image.remove()
  }
  return template.innerHTML
})

function isRemoteImage(source: string): boolean {
  if (!source) return false
  try {
    const base = new URL(document.baseURI)
    const url = new URL(source, base)
    return url.protocol !== 'data:' && url.protocol !== 'blob:' && url.origin !== base.origin
  } catch {
    return true
  }
}
</script>

<style scoped>
.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
  font-size: 1rem;
}

.markdown-body :deep(tr) {
  background-color: transparent !important;
}

.markdown-body :deep(pre),
.markdown-body :deep(code) {
  background-color: var(--p-content-hover-background) !important;
  color: var(--p-text-color) !important;
}
</style>
