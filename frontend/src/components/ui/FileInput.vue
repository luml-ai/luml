<template>
  <div
    ref="dropzoneRef"
    class="dropzone"
    :class="{ active: dropzoneActive }"
    @dragenter="onDragenter"
    @dragover.prevent="onDragover"
    @dragleave.prevent="onDragleave"
    @drop.prevent="onDrop">
    <div v-if="loading" class="loading-view">
      <progress-spinner style="width: 48px; height: 48px" />
      <div>{{ loadingMessage ? loadingMessage : 'Loading' }}</div>
    </div>
    <template v-else>
      <component :is="iconComponent" width="48" height="48" class="icon" :class="currentState" />
      <div class="content">
        <template v-if="currentState === 'success'">
          <div class="file-info">
            <div v-if="successMessageOnly">
              {{ successMessageOnly }} <br />
              <button v-if="successRemoveText" type="button" class="link" @click="removeFile">
                {{ successRemoveText }}
              </button>
            </div>
            <template v-else>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ sizeText }}</span>
              <d-button severity="danger" rounded variant="text" @click="removeFile">
                <template #icon>
                  <trash2 width="14" height="14" />
                </template>
              </d-button>
            </template>
          </div>
        </template>
        <template v-else-if="currentState === 'error'">
          <div class="title">
            Something went wrong. Please check your file and
            <label :for="id" class="accent">try again</label>
            .
          </div>
        </template>
        <template v-else>
          <div class="title">
            <span class="drag-drop-text">Drag and drop, or </span>
            <label :for="id" class="accent">{{ uploadText }}</label>
          </div>
          <div class="help-text">{{ acceptText }}</div>
        </template>
        <input ref="inputRef" :id="id" type="file" @change="inputChange" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, BadgeCheck, BadgeX, Trash2 } from 'lucide-vue-next'
import { ProgressSpinner } from 'primevue'
import { useToast } from 'primevue'
import { incorrectFileTypeErrorToast } from '@/lib/primevue/data/toasts'

const toast = useToast()

type Emits = {
  selectFile: [File]
  removeFile: []
}
type Props = {
  file: {
    name?: string
    size?: number
  }
  error: boolean
  id: string
  acceptText: string
  uploadText: string
  accept?: string[]
  loading?: boolean
  loadingMessage?: string
  successMessageOnly?: string
  successRemoveText?: string
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const dropzoneRef = ref()
const inputRef = ref<HTMLInputElement | null>(null)
const dropzoneActive = ref(false)

const currentState = computed(() => {
  if (props.loading) return 'loading'
  else if (props.error) return 'error'
  else if (props.file.name && props.file.size) return 'success'
  else return 'default'
})

const iconComponent = computed(() => {
  switch (currentState.value) {
    case 'success':
      return BadgeCheck
    case 'error':
      return BadgeX
    default:
      return Download
  }
})
const sizeText = computed(() => {
  if (!props.file.size) return `0 KB`
  if (props.file.size < 1024 * 1024) return `${(props.file.size / 1024).toFixed(3)} KB`
  else return `${(props.file.size / (1024 * 1024)).toFixed(3)} MB`
})

function onDragenter() {
  dropzoneActive.value = true
}
function onDragleave(e: DragEvent) {
  if (dropzoneRef.value && !dropzoneRef.value.contains(e.relatedTarget)) {
    dropzoneActive.value = false
  }
}
function onDragover() {}
function onDrop(e: DragEvent) {
  dropzoneActive.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) selectFile(file)
}
function inputChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) selectFile(file)
}
function selectFile(file: File) {
  if (props.accept && !props.accept.includes(file.type)) toast.add(incorrectFileTypeErrorToast)
  else emit('selectFile', file)
}
function removeFile() {
  emit('removeFile')
  const input = inputRef.value
  if (input) input.value = ''
}
</script>

<style scoped>
.dropzone {
  padding: 24px 48px;
  border-radius: 8px;
  border: 1px dashed var(--p-fileupload-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  height: 203px;
  width: 100%;
  gap: 36px;
  background-color: var(--p-fileupload-background);
  position: relative;
}

.dropzone.active {
  border-color: var(--p-fileupload-content-highlight-border-color);
}

.icon {
  flex: 0 0 auto;
  color: var(--p-text-link-color);
}

.icon.success {
  color: var(--p-badge-success-background);
}

.icon.error {
  color: var(--p-badge-danger-background);
}

.content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.title {
  font-size: 16px;
}

.accent {
  color: var(--p-text-link-color);
  cursor: pointer;
}

.accent:hover {
  text-decoration: underline;
}

.help-text {
  color: var(--p-text-muted-color);
}

input[type='file'] {
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
  position: absolute;
}

.file-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 7px 0;
}

.file-name {
  margin-right: 16px;
}

.file-size {
  margin-right: 12px;
  color: var(--p-text-muted-color);
}

.loading-view {
  display: flex;
  flex-direction: column;
  gap: 48px;
  align-items: center;
  text-align: center;
  font-weight: 500;
}

@media (max-width: 768px) {
  .dropzone {
    padding: 16px;
    gap: 16px;
  }
  .drag-drop-text {
    display: none;
  }
}
</style>
