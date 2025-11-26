import { ref, watch, onUnmounted, computed } from 'vue'
import { fetchFileContent } from '../components/orbits/tabs/registry/collection/model/modell-attachments/utils/fileContentFetcher'
import { downloadFileFromBlob } from '../helpers/helpers'
import type {
  UseFilePreviewProps,
  PreviewState,
} from '../components/orbits/tabs/registry/collection/model/modell-attachments/attachments.interfaces'

export function useFilePreview(props: UseFilePreviewProps) {
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const contentUrl = ref<string>('')
  const textContent = ref<string>('')
  const contentBlob = ref<Blob | null>(null)
  const mainModelUrl = ref<string | null>(null)

  const fetchMainModelUrl = async () => {
    if (mainModelUrl.value) return mainModelUrl.value

    try {
      const url = await props.getDownloadUrl(props.modelId.value)
      mainModelUrl.value = url
      return url
    } catch (e) {
      console.error('Failed to get model download URL', e)
      return null
    }
  }

  const loadFileContent = async () => {
    if (!props.file.value) return

    isLoading.value = true
    error.value = null
    textContent.value = ''
    contentBlob.value = null

    if (contentUrl.value) {
      URL.revokeObjectURL(contentUrl.value)
      contentUrl.value = ''
    }

    try {
      const url = await fetchMainModelUrl()
      if (!url) {
        throw new Error('No URL available')
      }

      const result = await fetchFileContent({
        file: props.file.value,
        fileIndex: props.fileIndex.value,
        downloadUrl: url,
      })

      if (result.error) {
        error.value = result.error
        return
      }

      if (result.blob) {
        contentBlob.value = result.blob
      }

      if (result.contentUrl) {
        contentUrl.value = result.contentUrl
      }

      if (result.text) {
        textContent.value = result.text
      }
    } catch (e: any) {
      console.error('Failed to load file content:', e)
      error.value = 'unknown'
    } finally {
      isLoading.value = false
    }
  }

  const downloadFile = async (fileName: string) => {
    if (!props.file.value || !props.file.value.path) return

    if (contentBlob.value) {
      downloadFileFromBlob(contentBlob.value, fileName)
      return
    }

    if (textContent.value) {
      const blob = new Blob([textContent.value], { type: 'text/plain' })
      downloadFileFromBlob(blob, fileName)
      return
    }

    try {
      isLoading.value = true
      const url = await fetchMainModelUrl()
      if (!url) return

      const rangeData = props.fileIndex.value[props.file.value.path]
      if (!rangeData) {
        throw new Error('File not found in index')
      }

      const [offset, length] = rangeData
      const end = offset + length - 1

      const response = await fetch(url, {
        headers: { Range: `bytes=${offset}-${end}` },
      })

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`)
      }

      const blob = await response.blob()
      downloadFileFromBlob(blob, fileName)
    } catch (e) {
      console.error('Failed to download file:', e)
    } finally {
      isLoading.value = false
    }
  }

  watch(() => props.file.value, loadFileContent)

  watch(
    () => props.modelId.value,
    () => {
      mainModelUrl.value = null
    },
  )

  onUnmounted(() => {
    if (contentUrl.value) {
      URL.revokeObjectURL(contentUrl.value)
    }
  })
  const previewState = computed<PreviewState>(() => {
    if (isLoading.value) return 'loading'

    switch (error.value) {
      case 'unsupported':
        return 'unsupported'
      case 'too-big':
        return 'too-big'
      case 'empty':
        return 'empty'
      case 'not-found':
      case 'unknown':
        return 'error'
      default:
        return null
    }
  })

  return {
    isLoading,
    error,
    contentUrl,
    textContent,
    contentBlob,
    fetchFileContent: loadFileContent,
    downloadFile,
    previewState,
  }
}
