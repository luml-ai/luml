<template>
  <div class="attachments-wrapper">
    <template v-if="isEmpty">
      <div class="empty-state">
        <p>This attachment is empty.</p>
      </div>
    </template>
    <template v-else>
      <FileTree :tree="provider.getTree()" :selected="selectedFile" @select="handleSelect" />
      <div class="file-preview card">
        <FilePreviewHeader
          v-if="selectedFile"
          :file-name="selectedFile.name"
          :file-size="selectedFile.size ?? 0"
          :file-path="selectedFile.path ?? ''"
          :is-downloading="isDownloading"
          @copy-path="handleCopyPath"
          @download="handleDownload"
        />
        <FilePreview
          ref="preview"
          v-if="selectedFile && source"
          :file-name="selectedFile.name"
          :file-size="selectedFile.size"
          :source="source"
          :supports-partial-preview="provider.supportsPartialPreview?.(selectedFile.path ?? '')"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useToast } from 'primevue'
import FileTree from './components/FileTree.vue'
import FilePreview from './components/FilePreview.vue'
import FilePreviewHeader from './components/preview/FilePreviewHeader.vue'
import type { ModelAttachmentsProvider, FileNode } from './interfaces/interfaces'

interface Props {
  provider: ModelAttachmentsProvider
}

const props = defineProps<Props>()

const toast = useToast()
const selectedFile = ref<FileNode | null>(null)
const preview = ref<InstanceType<typeof FilePreview>>()
const isDownloading = ref(false)

const source = computed(() => {
  const file = selectedFile.value
  const provider = props.provider
  if (!file?.path) return
  const path = file.path
  return async () =>
    provider.getPreviewSource
      ? provider.getPreviewSource(path, file.size)
      : (await provider.getAttachmentContent(path)).blob
})

const isEmpty = computed(() => props.provider.isEmpty())

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

async function handleDownload() {
  if (!selectedFile.value?.path || isDownloading.value) return
  try {
    isDownloading.value = true
    const { name, path } = selectedFile.value
    const blob =
      preview.value?.contentBlob ?? (await props.provider.getAttachmentContent(path)).blob
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = name
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(link.href)
  } catch (error) {
    console.error('Failed to download file:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to download file',
      life: 3000,
    })
  } finally {
    isDownloading.value = false
  }
}
</script>

<style scoped>
.attachments-wrapper {
  display: flex;
  gap: 16px;
}

.file-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 6px;
  overflow: hidden;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-form-field-float-label-color);
}
</style>
