<template>
  <p v-if="isLoading" class="text-sm text-muted-color">Loading code…</p>
  <div v-else class="flex flex-col gap-2 nowheel nodrag">
    <div class="flex justify-end gap-2">
      <template v-if="isEditing">
        <Button
          text
          severity="secondary"
          label="Cancel"
          size="small"
          :disabled="isSaving"
          @click="onCancel"
        />
        <Button
          label="Save"
          size="small"
          :loading="isSaving"
          :disabled="isSaving"
          @click="onSave"
        />
      </template>
      <Button v-else text severity="secondary" label="Edit" size="small" @click="onEdit">
        <template #icon>
          <Pencil :size="14" />
        </template>
      </Button>
    </div>

    <Message v-if="isConflicted" severity="warn" size="small" data-testid="edit-conflict">
      This cell changed after you started to edit it.
      <div class="flex gap-2 mt-2">
        <Button label="Overwrite" size="small" :disabled="isSaving" @click="onOverwrite" />
        <Button
          text
          severity="secondary"
          label="Keep theirs"
          size="small"
          :disabled="isSaving"
          @click="onKeepTheirs"
        />
      </div>
    </Message>

    <UiCodeEditor
      v-if="isEditing"
      v-model="draftSource"
      :aria-label="`source of ${props.slug}`"
      :max-height="props.fullHeight ? 'none' : '18rem'"
    />
    <!-- The same editor, locked: highlighted and numbered before anybody edits. -->
    <UiCodeEditor
      v-else
      :model-value="source"
      readonly
      :aria-label="`source of ${props.slug}, read only`"
      :max-height="props.fullHeight ? 'none' : '18rem'"
    />

    <CreateLaneDialog
      v-if="editContext"
      v-model:visible="isForkPromptVisible"
      fork-required
      :from="editContext.branch"
      @created="onForked"
    />
  </div>
</template>

<script setup lang="ts">
import type { NotebookCodeProps } from '@/components/notebooks/cell/cell.interface'
import { ref } from 'vue'
import { Button, Message } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { Pencil } from 'lucide-vue-next'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore, type CellEditContext } from '@/store/flow'
import { useCellPanelPayload } from '@/composables/useCellPanelPayload'
import { WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import CreateLaneDialog from '@/components/notebooks/lanes/CreateLaneDialog.vue'

const props = defineProps<NotebookCodeProps>()

const flowStore = useFlowStore()
const toast = useToast()

const source = ref('')
const loadedContext = ref<CellEditContext | null>(null)
const draftSource = ref('')
/** Where the draft goes: the context of the source it began from, until a fork moves it. */
const editContext = ref<CellEditContext | null>(null)
const isEditing = ref(false)
const isSaving = ref(false)
const isConflicted = ref(false)
const isForkPromptVisible = ref(false)

// A draft and its edit context outlive a reload: only the read-only source
// under them follows the cell, and a newer version surfaces on save.
const { isLoading, reload: load } = useCellPanelPayload({
  slug: () => props.slug,
  follows: (cell) => cell.changed_step,
  fetch: () => flowStore.fetchCellSource(props.slug),
  onLoaded: (loaded) => {
    source.value = loaded.source
    loadedContext.value = loaded.context
  },
  onFailed: (error) => toast.add(errorToast(error, 'Failed to load code')),
})

function onEdit() {
  if (!flowStore.ensureOnLaneHead()) return
  if (!loadedContext.value) return
  draftSource.value = source.value
  editContext.value = loadedContext.value
  isEditing.value = true
}

function closeEditing() {
  isEditing.value = false
  isConflicted.value = false
  editContext.value = null
}

function onCancel() {
  closeEditing()
}

async function onSave() {
  const context = editContext.value
  if (!context) return
  isSaving.value = true
  try {
    // A draft can outlive a rewind of its lane, so the guard that gated the
    // edit is asked again, of the lane the edit goes to.
    if (await flowStore.isLaneBehindHead(context.branch, context.flow)) {
      isForkPromptVisible.value = true
      return
    }
    await land(context)
  } catch (error) {
    toast.add(errorToast(error, 'Failed to save code'))
  } finally {
    isSaving.value = false
  }
}

async function onForked(lane: string) {
  if (!editContext.value) return
  editContext.value = { ...editContext.value, branch: lane }
  isSaving.value = true
  try {
    await land(editContext.value)
  } finally {
    isSaving.value = false
  }
}

async function onOverwrite() {
  if (!editContext.value) return
  isSaving.value = true
  try {
    await land(editContext.value, { force: true })
  } finally {
    isSaving.value = false
  }
}

async function onKeepTheirs() {
  closeEditing()
  await load()
}

async function land(context: CellEditContext, options: { force?: boolean } = {}) {
  try {
    await flowStore.editCellSource(props.slug, draftSource.value, context, options)
  } catch (error) {
    if (error instanceof WorkspaceRefusedError && error.kind === 'EditConflict') {
      isConflicted.value = true
      return
    }
    isConflicted.value = false
    toast.add(errorToast(error, 'Failed to save code'))
    return
  }
  toast.add(successToast('Code saved successfully'))
  // The reload rebuilds the edit context, so the next save starts from this one.
  closeEditing()
  await load()
}
</script>
