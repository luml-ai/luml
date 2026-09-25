<template>
  <div class="flow-code-editor min-w-0" :style="{ '--flow-code-max-height': maxHeight }">
    <div ref="host" />
    <!-- The same slab the read-only view renders, so the surface does not jump
         while the editor's chunk is still on the wire. -->
    <pre v-if="!ready" :class="CODE_SURFACE_CLASS" :style="{ maxHeight }">{{ model }}</pre>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { CodeEditorHandle } from './codeMirror'
import { CODE_SURFACE_CLASS } from './codeSurface'

/**
 * The code editing surface: CodeMirror 6 over Python, fetched on mount so the
 * workbench's first chunk never carries it.
 *
 * It owns the typing and nothing else — no save, no cancel, no notion of a
 * version. The card above it keeps those, which is why swapping the editor out
 * again would change no contract.
 */
const props = withDefaults(
  defineProps<{
    /** Locked: the same rendering, no caret and no way to type into it. */
    readonly?: boolean
    /** Where the surface starts scrolling instead of growing. */
    maxHeight?: string
    ariaLabel?: string
  }>(),
  { readonly: false, maxHeight: '18rem', ariaLabel: 'cell source' },
)

const model = defineModel<string>({ required: true })

const host = ref<HTMLElement | null>(null)
const editor = shallowRef<CodeEditorHandle | null>(null)
const ready = ref(false)
/** A mount that finished after the card closed must not attach anything. */
let live = true

onMounted(async () => {
  const { mountCodeEditor } = await import('./codeMirror')
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

// A document the editor itself produced is already in it; `setSource` compares
// before dispatching, so binding both ways cannot loop.
watch(model, (source) => editor.value?.setSource(source))
watch(
  () => props.readonly,
  (locked) => editor.value?.setReadonly(locked),
)

defineExpose({ editor })
</script>

<style scoped>
/**
 * The palette CodeMirror's theme reads. Both halves are named off the app's
 * theme tokens where one exists; the syntax colours are the house slate/blue
 * family rather than a stock editor theme's.
 */
.flow-code-editor {
  --flow-code-font: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  --flow-code-bg: var(--p-surface-50, #f8fafc);
  --flow-code-border: var(--p-surface-200, #e2e8f0);
  --flow-code-fg: var(--p-text-color, #334155);
  --flow-code-gutter: var(--p-text-muted-color, #64748b);
  --flow-code-comment: var(--p-text-muted-color, #64748b);
  --flow-code-accent: var(--p-primary-color, #2673fd);
  --flow-code-active: #0f172a0a;
  --flow-code-selection: #2673fd2e;
  --flow-code-bracket: #2673fd33;
  --flow-code-keyword: #7c3aed;
  --flow-code-string: #047857;
  --flow-code-number: #b45309;
  --flow-code-function: #2563eb;
  --flow-code-type: #0e7490;
  --flow-code-property: #0f766e;
  --flow-code-builtin: #c2410c;
  --flow-code-meta: #a16207;
  --flow-code-punct: #64748b;
  --flow-code-invalid: #dc2626;
}

[data-theme='dark'] .flow-code-editor {
  --flow-code-bg: var(--p-surface-800, #27272a);
  --flow-code-border: var(--p-surface-700, #3f3f46);
  --flow-code-active: #ffffff0d;
  --flow-code-selection: #60a5fa3d;
  --flow-code-bracket: #60a5fa40;
  --flow-code-keyword: #c4b5fd;
  --flow-code-string: #6ee7b7;
  --flow-code-number: #fcd34d;
  --flow-code-function: #93c5fd;
  --flow-code-type: #67e8f9;
  --flow-code-property: #5eead4;
  --flow-code-builtin: #fdba74;
  --flow-code-meta: #fcd34d;
  --flow-code-punct: #a1a1aa;
  --flow-code-invalid: #fca5a5;
}
</style>
