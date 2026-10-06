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
            <Button label="save" :disabled="disabled" @click="saveEdit" />
          </template>
          <Button
            v-else
            text
            severity="secondary"
            label="edit"
            :disabled="disabled"
            @click="startEdit"
          >
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button } from 'primevue'
import { Pencil } from 'lucide-vue-next'
import type { FlowCell, ParamValue } from '../../model/types'
import SourceEditor from './SourceEditor.vue'
import { CODE_SURFACE_CLASS } from './codeSurface'

const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
  disabled?: boolean
}>()

const emit = defineEmits<{
  edit: [payload: { source: string }]
  'edit-start': []
}>()

const editing = defineModel<boolean>('editing', { default: false })
const draftSource = defineModel<string>('draft', { default: '' })

const sourceClass = computed(() => [
  CODE_SURFACE_CLASS,
  props.density === 'canvas' ? 'max-h-72' : 'max-h-96',
])

const editorHeight = computed(() => (props.density === 'canvas' ? '18rem' : '24rem'))

const paramNames = computed(() => Object.keys(props.cell.params))

function displayOf(value: ParamValue): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function startEdit(): void {
  if (props.disabled) return
  draftSource.value = props.cell.source
  editing.value = true
  emit('edit-start')
}

function saveEdit(): void {
  emit('edit', { source: draftSource.value })
}

function cancelEdit(): void {
  editing.value = false
}
</script>
