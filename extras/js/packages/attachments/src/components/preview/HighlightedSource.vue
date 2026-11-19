<template>
  <div ref="host" class="highlighted-source" />
</template>

<script setup lang="ts">
import { EditorState } from '@codemirror/state'
import { EditorView, lineNumbers } from '@codemirror/view'
import { ref, watchPostEffect } from 'vue'
import { languageExtension, previewHighlighting } from '../../utils/codeHighlighting'
import type { PreviewLanguage } from '../../utils/fileTypes'

const props = defineProps<{ source: string; language?: PreviewLanguage; fileName: string }>()
const host = ref<HTMLElement>()

watchPostEffect((onCleanup) => {
  if (!host.value) return

  const view = new EditorView({
    parent: host.value,
    doc: props.source,
    extensions: [
      lineNumbers(),
      EditorState.readOnly.of(true),
      EditorView.editable.of(false),
      EditorView.contentAttributes.of({
        'aria-label': `Contents of ${props.fileName}`,
        'aria-readonly': 'true',
        tabindex: '0',
      }),
      props.language ? languageExtension(props.language) : [],
      previewHighlighting,
    ],
  })
  onCleanup(() => view.destroy())
})
</script>

<style scoped>
.highlighted-source {
  --ui-code-keyword: #7c3aed;
  --ui-code-string: #047857;
  --ui-code-number: #b45309;
  --ui-code-function: #2563eb;
  --ui-code-type: #0e7490;
  --ui-code-property: #0f766e;
  --ui-code-builtin: #c2410c;
  --ui-code-meta: #a16207;
  --ui-code-punct: #64748b;
  --ui-code-invalid: #dc2626;
  --ui-code-comment: var(--p-text-muted-color, #64748b);
}

[data-theme='dark'] .highlighted-source {
  --ui-code-keyword: #c4b5fd;
  --ui-code-string: #6ee7b7;
  --ui-code-number: #fcd34d;
  --ui-code-function: #93c5fd;
  --ui-code-type: #67e8f9;
  --ui-code-property: #5eead4;
  --ui-code-builtin: #fdba74;
  --ui-code-meta: #fcd34d;
  --ui-code-punct: #a1a1aa;
  --ui-code-invalid: #fca5a5;
}

.highlighted-source :deep(.cm-scroller) {
  font-family: var(
    --ui-code-font,
    var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)
  );
  line-height: 1.625;
}

.highlighted-source :deep(.cm-gutters) {
  background: var(--p-content-background);
  color: var(--ui-code-gutter, var(--p-text-muted-color));
  border: none;
}
</style>
