<template>
  <div class="flex flex-col gap-4">
    <div v-if="paramNames.length" class="flex flex-col gap-2">
      <p class="text-sm text-muted-color">params</p>
      <div class="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1 max-w-md">
        <template v-for="name in paramNames" :key="name">
          <span class="font-mono text-sm text-muted-color">{{ name }}</span>
          <span class="font-mono text-sm">{{ displayOf(cell.params[name]) }}</span>
        </template>
      </div>
    </div>

    <div class="flex flex-col gap-1.5">
      <div class="flex items-center justify-end gap-2">
        <div class="flex items-center gap-1">
          <template v-if="editing">
            <Button text severity="secondary" label="cancel" @click="cancelEdit" />
            <Button label="save" @click="saveEdit" />
          </template>
          <Button v-else text severity="secondary" label="edit" @click="startEdit">
            <template #icon><Pencil :size="14" /></template>
          </Button>
        </div>
      </div>

      <SourceEditor
        v-if="editing"
        v-model="draftSource"
        :max-height="editorHeight"
        :aria-label="`source of ${cell.slug}`"
      />
      <pre v-else :class="sourceClass">{{ cell.source.trimEnd() }}</pre>

      <p
        v-if="cell.pendingProjection"
        class="flex items-center gap-1.5 text-sm text-(--p-message-info-color)"
      >
        <Info :size="14" class="shrink-0" />
        saved · not yet written to files
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button } from 'primevue'
import { Info, Pencil } from 'lucide-vue-next'
import type { FlowCell, ParamValue } from '../../model/types'
import SourceEditor from './SourceEditor.vue'
import { CODE_SURFACE_CLASS } from './codeSurface'

/**
 * The code tab: read-only source with an edit toggle onto a real code editor,
 * and the declared params above it. The gesture is what it always was — save
 * emits, a version lands — the surface underneath it is the part that changed.
 *
 * Params render, and do not edit. They are a dormant slot in v1 — parsed,
 * recorded as provenance, and reserved for the inspector and the sweep UI that
 * will read them — so the only way to change one is to change the cell, which
 * is the edit the source box below already is. An "apply" button here would
 * have written a params-only version through a second door.
 */
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
}>()

const emit = defineEmits<{
  edit: [payload: { source: string }]
  /**
   * The editor is open. What the edit is *based on* is fixed here rather than at
   * save: a head that moves while the reader is typing is exactly the conflict
   * the optimistic lock exists to catch, and reading the base at save time would
   * hand the daemon the version the edit was never written against.
   */
  'edit-start': []
}>()

const sourceClass = computed(() => [
  CODE_SURFACE_CLASS,
  props.density === 'canvas' ? 'max-h-72' : 'max-h-96',
])

/** The editor scrolls where the read-only slab does — same box, same density. */
const editorHeight = computed(() => (props.density === 'canvas' ? '18rem' : '24rem'))

// --- params ---------------------------------------------------------------

const paramNames = computed(() => Object.keys(props.cell.params))

function displayOf(value: ParamValue): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

// --- source ---------------------------------------------------------------

const editing = ref(false)
const draftSource = ref('')

function startEdit(): void {
  draftSource.value = props.cell.source
  editing.value = true
  emit('edit-start')
}

function saveEdit(): void {
  emit('edit', { source: draftSource.value })
  editing.value = false
}

function cancelEdit(): void {
  editing.value = false
}
</script>
