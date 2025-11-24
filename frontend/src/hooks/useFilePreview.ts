import { ref, watch, onUnmounted, type Ref } from 'vue'
import { getFileType } from '../components/orbits/tabs/registry/collection/model/modell-attachments/utils/fileTypes'

interface FileNode {
  name: string
  path?: string
  type: 'file' | 'folder'
  size?: number
}

interface UseFilePreviewProps {
  file: Ref<FileNode | null>
  fileIndex: Ref<Record<string, [number, number]>>
  modelId: Ref<string>
  getDownloadUrl: (modelId: string) => Promise<string>
}

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

  const fetchFileContent = async () => {
    if (!props.file.value || !props.file.value.path || props.file.value.type !== 'file') return

    const fileType = getFileType(props.file.value.name)
    if (!fileType) return

    isLoading.value = true
    error.value = null
    textContent.value = ''
    contentBlob.value = null
    if (contentUrl.value) URL.revokeObjectURL(contentUrl.value)
    contentUrl.value = ''

    try {
      const url = await fetchMainModelUrl()
      if (!url) throw new Error('No URL available')

      const rangeData = props.fileIndex.value[props.file.value.path]
      if (!rangeData) {
        throw new Error('File not found in index map')
      }

      const [offset, length] = rangeData
      if (length === 0) {
        error.value = 'empty'
        isLoading.value = false
        return
      }

      const MAX_PREVIEW_SIZE = 10 * 1024 * 1024
      if (length > MAX_PREVIEW_SIZE) {
        error.value = 'too-big'
        isLoading.value = false
        return
      }

      const end = offset + length - 1
      const response = await fetch(url, {
        headers: { Range: `bytes=${offset}-${end}` },
      })

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`)
      }

      const blob = await response.blob()
      contentBlob.value = blob

      if (fileType === 'image') {
        contentUrl.value = URL.createObjectURL(blob)
      } else if (fileType === 'svg') {
        const svgText = await blob.text()
        const sanitizedSvg = svgText.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
        const svgBlob = new Blob([sanitizedSvg], { type: 'image/svg+xml' })
        contentUrl.value = URL.createObjectURL(svgBlob)
      } else if (fileType === 'audio' || fileType === 'video') {
        contentUrl.value = URL.createObjectURL(blob)
      } else if (fileType === 'pdf') {
        const pdfBlob = new Blob([blob], { type: 'application/pdf' })
        contentUrl.value = URL.createObjectURL(pdfBlob)
      } else if (fileType === 'text' || fileType === 'code') {
        textContent.value = await blob.text()
        const ext = props.file.value.name.split('.').pop()?.toLowerCase()
        if (ext === 'json') {
          try {
            textContent.value = JSON.stringify(JSON.parse(textContent.value), null, 2)
          } catch {}
        }
      } else if (fileType === 'html') {
        let htmlText = await blob.text()

        htmlText = htmlText.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
        htmlText = await convertImagesToBlob(htmlText)

        const htmlBlob = new Blob([htmlText], { type: 'text/html' })
        contentUrl.value = URL.createObjectURL(htmlBlob)
      }

      return { blob, text: textContent.value }
    } catch (e: any) {
      console.error(e)
    } finally {
      isLoading.value = false
    }
  }

  const downloadFile = async (fileName: string) => {
    if (!props.file.value || !props.file.value.path) return

    if (contentUrl.value) {
      triggerDownload(contentUrl.value, fileName)
      return
    }

    if (textContent.value) {
      const blob = new Blob([textContent.value], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      triggerDownload(url, fileName)
      URL.revokeObjectURL(url)
      return
    }

    try {
      isLoading.value = true
      const url = await fetchMainModelUrl()
      if (!url) return
      const [offset, length] = props.fileIndex.value[props.file.value.path]!
      const response = await fetch(url, {
        headers: { Range: `bytes=${offset}-${offset + length - 1}` },
      })
      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)
      triggerDownload(blobUrl, fileName)
      URL.revokeObjectURL(blobUrl)
    } catch (e) {
      console.error(e)
    } finally {
      isLoading.value = false
    }
  }

  const triggerDownload = (url: string, name: string) => {
    const link = document.createElement('a')
    link.href = url
    link.download = name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  watch(() => props.file.value, fetchFileContent)
  watch(
    () => props.modelId.value,
    () => {
      mainModelUrl.value = null
    },
  )

  onUnmounted(() => {
    if (contentUrl.value) URL.revokeObjectURL(contentUrl.value)
  })

  return {
    isLoading,
    error,
    contentUrl,
    textContent,
    contentBlob,
    fetchFileContent,
    downloadFile,
  }
}

async function convertImagesToBlob(htmlText: string): Promise<string> {
  const parser = new DOMParser()
  const doc = parser.parseFromString(htmlText, 'text/html')
  const images = Array.from(doc.querySelectorAll('img'))
  for (const img of images) {
    const src = img.getAttribute('src')
    if (!src) continue
    try {
      const response = await fetch(src)
      if (!response.ok) continue

      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)

      img.setAttribute('src', objectUrl)
    } catch (e) {
      console.warn('Failed', src, e)
    }
  }

  return doc.documentElement.outerHTML
}
