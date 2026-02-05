import { ref, watch, onUnmounted } from 'vue'
import { getFileType } from '../utils/fileTypes'
import { processFileContent } from '../utils/fileContentProcessors'
import type { PreviewState, UseFilePreviewOptions } from '../interfaces/interfaces'
const MAX_PREVIEW_SIZE = 10 * 1024 * 1024

export function useFilePreview(options: UseFilePreviewOptions) {
  const { file, provider } = options

  const error = ref<string | null>(null)
  const contentUrl = ref<string | null>(null)
  const textContent = ref<string | null>(null)
  const contentBlob = ref<Blob | null>(null)
  const previewState = ref<PreviewState>(null)

  const cleanup = () => {
    if (contentUrl.value) {
      URL.revokeObjectURL(contentUrl.value)
      contentUrl.value = null
    }
    textContent.value = null
    contentBlob.value = null
    error.value = null
  }

  const loadContent = async () => {
    cleanup()

    const currentFile = file.value
    const currentProvider = provider.value

    if (!currentFile || !currentProvider) {
      previewState.value = null
      return
    }

    if (!currentFile.path || currentFile.type !== 'file') {
      previewState.value = null
      return
    }

    const fileType = getFileType(currentFile.name)
    if (!fileType) {
      error.value = 'This file type is not supported for preview'
      previewState.value = 'unsupported'
      return
    }

    if (currentFile.size && currentFile.size > MAX_PREVIEW_SIZE) {
      error.value = 'File is too large for preview (max 10 MB)'
      previewState.value = 'too-big'
      return
    }

    previewState.value = 'loading'

    try {
      const content = await currentProvider.getAttachmentContent(currentFile.path)

      if (content.size === 0) {
        error.value = 'File is empty'
        previewState.value = 'empty'
        return
      }

      const processed = await processFileContent(content.blob, fileType, currentFile.name)

      contentUrl.value = processed.contentUrl ?? null
      textContent.value = processed.text ?? null
      contentBlob.value = content.blob
      previewState.value = null
    } catch (e) {
      console.error('Failed to load file content:', e)
      error.value = e instanceof Error ? e.message : 'Failed to load file'
      previewState.value = 'error'
    }
  }

  const downloadFile = (fileName: string) => {
    if (!contentBlob.value) return

    const url = URL.createObjectURL(contentBlob.value)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  watch(file, loadContent, { immediate: true })

  onUnmounted(() => {
    cleanup()
  })

  return {
    error,
    contentUrl,
    textContent,
    contentBlob,
    previewState,
    downloadFile,
  }
}
