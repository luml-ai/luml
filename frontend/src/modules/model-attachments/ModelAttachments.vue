<template>
  <div class="attachments-wrapper">
    <template v-if="isEmpty">
      <div class="empty-state">
        <p>This attachment is empty.</p>
      </div>
    </template>
    <template v-else>
      <FileTree :tree="provider.getTree()" :selected="selectedFile" @select="handleSelect" />
      <FilePreview
        :file-name="fileName"
        :file-size="fileSize"
        :file-path="filePath"
        :file-type="fileType"
        :preview-state="previewState"
        :error-message="previewError || undefined"
        :content-url="contentUrl"
        :text-content="textContent"
        :content-blob="contentBlob"
        @copy-path="handleCopyPath"
        @download="handleDownload"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useToast } from 'primevue'
import FileTree from './components/FileTree.vue'
import FilePreview from './components/FilePreview.vue'
import { useFilePreview } from './hooks/useFilePreview'
import { getFileType } from './utils/fileTypes'
import type { ModelAttachmentsProvider, FileNode } from './interfaces/interfaces'

interface Props {
  provider: ModelAttachmentsProvider
}

const props = defineProps<Props>()

const toast = useToast()
const selectedFile = ref<FileNode | null>(null)

const {
  error: previewError,
  contentUrl,
  textContent,
  contentBlob,
  downloadFile,
  previewState,
} = useFilePreview({
  file: toRef(() => selectedFile.value),
  provider: toRef(() => props.provider),
})

const isEmpty = computed(() => props.provider.isEmpty())
const fileName = computed(() => selectedFile.value?.name || '')
const fileSize = computed(() => selectedFile.value?.size || 0)
const filePath = computed(() => selectedFile.value?.path || '')
const fileType = computed(() => (selectedFile.value ? getFileType(selectedFile.value.name) : null))

function handleSelect(node: FileNode) {
  if (node.type === 'file') {
    selectedFile.value = node
  }
}

async function handleCopyPath() {
  if (!selectedFile.value?.path) return
  try {
    await navigator.clipboard.writeText(selectedFile.value.path)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Path copied to clipboard',
      life: 3000,
    })
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to copy path to clipboard',
      life: 3000,
    })
  }
}

function handleDownload() {
  if (!selectedFile.value) return
  downloadFile(selectedFile.value.name)
}
</script>

<style scoped>
.attachments-wrapper {
  display: flex;
  gap: 16px;
  height: calc(100vh - 320px);
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-form-field-float-label-color);
}
</style>
