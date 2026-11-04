<template>
  <div class="ui-code-editor min-w-0" :style="{ '--ui-code-max-height': maxHeight }">
    <div ref="host" />
    <pre v-if="!ready" :class="CODE_SURFACE_CLASS" :style="{ maxHeight }">{{ model }}</pre>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { CodeEditorHandle } from './code-editor.interface'

const CODE_SURFACE_CLASS =
  'font-mono text-sm leading-relaxed rounded-lg bg-surface-50 dark:bg-surface-800 p-3 overflow-auto'

const props = withDefaults(
  defineProps<{
    readonly?: boolean
    maxHeight?: string
    ariaLabel?: string
  }>(),
  { readonly: false, maxHeight: '18rem', ariaLabel: 'code editor' },
)

const model = defineModel<string>({ required: true })

const host = ref<HTMLElement | null>(null)
const editor = shallowRef<CodeEditorHandle | null>(null)
const ready = ref(false)
let live = true

onMounted(async () => {
  const { mountCodeEditor } = await import('./code-editor.const')
  if (!live || !host.value) return
  editor.value = mountCodeEditor({
    parent: host.value,
    doc: model.value,
    readonly: props.readonly,
    ariaLabel: props.ariaLabel,
    onChange: (source) => {
      model.value = source
    },
  })
  ready.value = true
})

onBeforeUnmount(() => {
  live = false
  editor.value?.destroy()
})

watch(model, (source) => editor.value?.setSource(source))
watch(
  () => props.readonly,
  (locked) => editor.value?.setReadonly(locked),
)

defineExpose({ editor })
</script>

<style scoped>
.ui-code-editor {
  --ui-code-font: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  --ui-code-bg: var(--p-surface-50, #f8fafc);
  --ui-code-border: var(--p-surface-200, #e2e8f0);
  --ui-code-fg: var(--p-text-color, #334155);
  --ui-code-gutter: var(--p-text-muted-color, #64748b);
  --ui-code-comment: var(--p-text-muted-color, #64748b);
  --ui-code-accent: var(--p-primary-color, #2673fd);
  --ui-code-active: #0f172a0a;
  --ui-code-selection: #2673fd2e;
  --ui-code-bracket: #2673fd33;
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
}

[data-theme='dark'] .ui-code-editor {
  --ui-code-bg: var(--p-surface-800, #27272a);
  --ui-code-border: var(--p-surface-700, #3f3f46);
  --ui-code-active: #ffffff0d;
  --ui-code-selection: #60a5fa3d;
  --ui-code-bracket: #60a5fa40;
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
</style>
