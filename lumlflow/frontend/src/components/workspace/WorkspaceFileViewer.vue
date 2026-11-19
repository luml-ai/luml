<template>
  <Card class="viewer" :class="{ locked: lock }" :style="{ '--agent-color': agentColor }">
    <template #content>
      <div class="viewer-inner">
        <header class="flex items-start justify-between gap-4 pb-4">
          <div class="min-w-0">
            <div class="flex flex-wrap items-baseline gap-x-2.5">
              <span class="font-medium break-all">{{ file.name }}</span>
              <span class="text-sm text-muted-color">
                {{ file.size === null ? 'Unknown size' : getSizeText(file.size, ' ') }}
                · Modified {{ dateToText(file.modified_at, 'minute') }}
              </span>
            </div>
            <div class="mt-2 flex items-center gap-1.5 text-muted-color">
              <span class="break-all text-sm">{{ file.path }}</span>
              <Button
                text
                severity="secondary"
                class="icon-button"
                aria-label="Copy path"
                @click="copy"
              >
                <template #icon><component :is="copied ? Check : Copy" :size="18" /></template>
              </Button>
            </div>
          </div>
          <Button
            text
            severity="secondary"
            class="icon-button"
            aria-label="Close preview"
            @click="emit('close')"
          >
            <template #icon><X :size="18" /></template>
          </Button>
        </header>

        <div
          v-if="lock"
          class="live-strip"
          role="status"
          title="Read-only until 3 minutes after the agent's last change to this file."
        >
          <Lock :size="14" class="shrink-0" />
          <span class="truncate"
            >{{ lock.label === 'an agent' ? 'An agent' : lock.label }} is working on this file</span
          >
        </div>

        <div class="viewer-body" :class="{ 'opacity-60': lock }">
          <Message v-if="gone && editBase" severity="warn">This file was moved or deleted</Message>
          <div v-if="editBase" class="edit-actions">
            <Button
              text
              size="small"
              severity="secondary"
              label="Cancel"
              :disabled="saving"
              @click="discard"
            />
            <Button
              label="Save"
              size="small"
              :disabled="readOnly || conflict"
              @click="save(false)"
            />
          </div>
          <Message v-if="editBase && conflict && !gone && !lock" severity="warn" size="small">
            This file changed on disk after you started to edit it.
            <div class="mt-2 flex gap-2">
              <Button label="Overwrite" size="small" :disabled="saving" @click="save(true)" />
              <Button
                label="Reload"
                size="small"
                text
                severity="secondary"
                :disabled="saving"
                @click="reload"
              />
            </div>
          </Message>
          <UiCodeEditor
            v-if="editBase"
            v-model="draft"
            :readonly="readOnly"
            :language="getPreviewLanguage(file.name) ?? null"
            :aria-label="`Contents of ${file.name}`"
            max-height="none"
            class="flex-1 min-h-0 overflow-auto"
          />
          <template v-else>
            <div v-if="disk && !gone" class="edit-actions">
              <Button
                text
                size="small"
                severity="secondary"
                label="Edit"
                :disabled="!!lock || loading"
                @click="startEdit"
              >
                <template #icon><Pencil :size="14" /></template>
              </Button>
            </div>
            <div v-if="statusText" class="preview-state" role="status">{{ statusText }}</div>
            <FilePreview
              v-else-if="fileType && file.size !== null"
              :key="refreshKey"
              class="shared-preview"
              :file-name="file.name"
              :file-size="file.size"
              :source="workspaceApi.fileUrl(file.path)"
            />
            <pre v-else-if="disk" class="plain-text">{{ disk.text }}</pre>
          </template>
        </div>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { FilePreview, getFileExtension, getFileType, getPreviewLanguage } from '@luml/attachments'
import { Button, Card, Message, useToast } from 'primevue'
import { Check, Copy, Lock, Pencil, X } from 'lucide-vue-next'
import { workspaceApi, WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import type { WorkspaceFile, WorkspaceFileLock } from '@/api/slices/workspace/workspace.interface'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import { useCopy } from '@/composables/useCopy'
import { dateToText } from '@/helpers/date'
import { getErrorMessage } from '@/helpers/errors'
import { getSizeText } from '@/helpers/string'
import { AGENT_COLORS, useFlowStore } from '@/store/flow'
import { errorToast } from '@/toasts'

const props = defineProps<{
  file: WorkspaceFile
  gone: boolean
  locks?: WorkspaceFileLock[]
  refreshKey: number
}>()
const emit = defineEmits<{ close: []; saved: []; reloaded: []; dirty: [changed: boolean] }>()
const toast = useToast()
const flow = useFlowStore()
const { copy, copied } = useCopy(() => props.file.path)

type FileText = Awaited<ReturnType<typeof workspaceApi.readText>>
const disk = shallowRef<FileText>()
// The save must keep the version the editor opened, even after a watcher refresh.
const editBase = shallowRef<FileText>()
const draft = ref('')
const conflict = ref(false)
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
let readVersion = 0

const refusedLock = ref<{ label: string; actor?: string }>()
const lock = computed(
  () => props.locks?.find((entry) => entry.path === props.file.path) ?? refusedLock.value,
)
watch(
  () => props.locks,
  () => {
    refusedLock.value = undefined
  },
)
const fileType = computed(() => getFileType(props.file.name))
const isTextCandidate = computed(() => {
  const type = fileType.value
  const { size, name } = props.file
  return (
    !props.gone &&
    size !== null &&
    size <= 2 * 1024 * 1024 &&
    (type === 'text' || type === 'code' || (!type && getFileExtension(name) !== 'luml'))
  )
})
const agentColor = computed(() => {
  if (!lock.value?.actor) return 'var(--p-text-muted-color)'
  return (
    flow.pairedAgents.find((agent) => agent.actor === lock.value?.actor)?.color ?? AGENT_COLORS[0]
  )
})
const readOnly = computed(() => props.gone || !!lock.value || saving.value)
const statusText = computed(() => {
  if (props.gone) return 'This file was moved or deleted'
  if (props.file.size === null) return 'No preview for this file type'
  if (props.file.size === 0) return 'File is empty'
  if (fileType.value) return ''
  if (props.file.size > 10 * 1024 * 1024) return 'File is too large for preview'
  if (loading.value && !disk.value) return 'Loading preview…'
  return loadError.value || (disk.value ? '' : 'No preview for this file type')
})

watch(
  () => !!editBase.value && draft.value !== editBase.value.text,
  (dirty) => emit('dirty', dirty),
)

function discard() {
  editBase.value = undefined
  draft.value = ''
  conflict.value = false
}

function startEdit() {
  if (!disk.value || readOnly.value || loading.value) return
  editBase.value = disk.value
  draft.value = disk.value.text
}

async function refreshText() {
  const request = ++readVersion
  loadError.value = ''
  loading.value = isTextCandidate.value
  if (!isTextCandidate.value) {
    disk.value = undefined
    if (editBase.value) conflict.value = true
    return !props.gone && props.file.size !== null
  }
  try {
    const result = await workspaceApi.readText(props.file.path)
    if (request !== readVersion) return false
    disk.value = result
    if (
      editBase.value &&
      (result.revision !== editBase.value.revision || result.mtime_ns !== editBase.value.mtime_ns)
    ) {
      conflict.value = true
    }
    return true
  } catch (error) {
    if (request !== readVersion) return false
    disk.value = undefined
    if (
      error instanceof WorkspaceRefusedError &&
      (error.kind === 'NotText' || error.kind === 'TooLarge')
    ) {
      if (editBase.value) conflict.value = true
      return true
    }
    loadError.value = getErrorMessage(error)
    if (fileType.value || editBase.value) toast.add(errorToast(error))
    return false
  } finally {
    if (request === readVersion) loading.value = false
  }
}

watch(
  [
    () => props.file.path,
    () => props.file.modified_at,
    () => props.file.size,
    () => props.gone,
    () => props.refreshKey,
  ],
  ([path], [previousPath]) => {
    if (path !== previousPath) {
      discard()
      disk.value = undefined
      saving.value = false
    }
    void refreshText()
  },
  { immediate: true },
)
watch(lock, (lock) => {
  if (editBase.value && lock) conflict.value = true
})

async function reload() {
  const base = editBase.value
  if ((await refreshText()) && base === editBase.value) {
    discard()
    emit('reloaded')
  }
}

async function save(force: boolean) {
  const base = editBase.value
  if (!base || readOnly.value || (conflict.value && !force)) return
  saving.value = true
  const text = draft.value
  try {
    const result = await workspaceApi.writeText(
      props.file.path,
      text,
      base.mtime_ns,
      base.revision,
      force,
    )
    if (base !== editBase.value) return
    ++readVersion
    loading.value = false
    disk.value = { ...base, ...result, text }
    discard()
    emit('saved')
  } catch (error) {
    if (base !== editBase.value) return
    if (error instanceof WorkspaceRefusedError && error.kind === 'FileConflict')
      conflict.value = true
    else if (error instanceof WorkspaceRefusedError && error.kind === 'FileLocked') {
      const label = error.details.label ?? 'an agent'
      refusedLock.value = {
        label,
        actor: flow.pairedAgents.find((agent) => agent.label === label)?.actor,
      }
      conflict.value = true
    } else toast.add(errorToast(error))
  } finally {
    if (!editBase.value || base === editBase.value) saving.value = false
  }
}

onBeforeUnmount(() => {
  ++readVersion
  discard()
})
defineExpose({ discard, editTarget: computed(() => editBase.value?.target) })
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
.viewer.locked {
  border: 1px solid var(--agent-color);
}
.icon-button {
  padding: 2px;
  width: auto;
  flex-shrink: 0;
}
.live-strip {
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
.viewer-body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.shared-preview {
  padding: 0;
}
.shared-preview :deep(.content-image),
.shared-preview :deep(.content-media) {
  flex: 1;
  min-height: 0;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-content-background);
}
.shared-preview :deep(.content-image) {
  overflow: auto;
}
.shared-preview :deep(.content-audio audio) {
  max-width: 480px;
}
.shared-preview :deep(.content-video video) {
  max-height: 100%;
  background: #000;
  border-radius: 4px;
}
.shared-preview :deep(.preview-state:has(.state-content)) {
  border: 1px dashed var(--p-content-border-color);
  border-radius: 8px;
}
.viewer-body:has(.shared-preview .view-toggle) > .edit-actions {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 1;
}
.preview-state,
.plain-text {
  flex: 1;
  min-height: 0;
  padding: 0.75rem;
  border: 1px dashed var(--p-content-border-color);
  border-radius: 8px;
}
.preview-state {
  display: grid;
  place-items: center;
  color: var(--p-text-muted-color);
}
.plain-text {
  border-style: solid;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 0.875rem;
}
</style>
