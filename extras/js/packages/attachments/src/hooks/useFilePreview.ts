import { computed, ref, shallowRef, watch } from 'vue'
import type { AsyncBuffer } from 'hyparquet'
import { urlPreviewBytes } from '../utils/previewBytes'
import { getFileExtension, getFileType } from '../utils/fileTypes'
import { processFileContent } from '../utils/fileContentProcessors'
import { releasePreviewStreamUrl } from '../utils/previewStream'
import type { FilePreviewProps, PreviewState } from '../interfaces/interfaces'

const MAX_PREVIEW_SIZE = 10 * 1024 * 1024

async function fetchPreviewBlob(
  url: string,
  signal: AbortSignal,
  limitSize: boolean,
): Promise<Blob | null> {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`File request failed (${response.status})`)
  if (!limitSize) return response.blob()
  if (Number(response.headers.get('Content-Length')) > MAX_PREVIEW_SIZE) {
    await response.body?.cancel()
    return null
  }
  // A file may grow after listing, or the server may omit Content-Length.
  const reader = response.body?.getReader()
  const chunks: BlobPart[] = []
  let length = 0
  if (reader) {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      length += value.byteLength
      if (length > MAX_PREVIEW_SIZE) {
        await reader.cancel()
        return null
      }
      chunks.push(value)
    }
  }
  return new Blob(chunks, { type: response.headers.get('Content-Type') || '' })
}

function sizeState(size: number | undefined, limited: boolean) {
  if (size === 0) return 'empty'
  if (limited && size !== undefined && size > MAX_PREVIEW_SIZE) return 'too-big'
  return null
}

export function useFilePreview(props: FilePreviewProps) {
  const fileType = computed(() => getFileType(props.fileName))
  const error = ref('')
  const contentUrl = ref('')
  const textContent = ref('')
  const contentBlob = shallowRef<Blob>()
  const parquetFile = shallowRef<AsyncBuffer>()
  const previewState = ref<PreviewState>(null)

  watch(
    () =>
      [
        props.fileName,
        props.source,
        props.fileSize,
        props.supportsPartialPreview,
        props.datasetSplit,
      ] as const,
    async ([name, source, fileSize, supportsPartialPreview, datasetSplit], _, onCleanup) => {
      let active = true
      let ownedUrl: string | undefined
      let streamUrl: string | undefined
      const controller = new AbortController()
      onCleanup(() => {
        active = false
        controller.abort()
        if (ownedUrl) URL.revokeObjectURL(ownedUrl)
        if (streamUrl) releasePreviewStreamUrl(streamUrl)
      })

      error.value = ''
      contentUrl.value = ''
      textContent.value = ''
      contentBlob.value = undefined
      parquetFile.value = undefined
      const type = fileType.value
      const streamed = type === 'audio' || type === 'video' || type === 'pdf'
      const parquet = getFileExtension(name) === 'parquet'
      if (!type) {
        previewState.value = 'unsupported'
        return
      }

      const partial =
        (streamed || parquet) && (typeof source !== 'function' || supportsPartialPreview)
      const limitSize = !partial && !(datasetSplit && type === 'table')
      // A range provider rechecks the length when opening a listed attachment.
      const listedSize = partial && typeof source === 'function' ? undefined : fileSize
      previewState.value = sizeState(listedSize, limitSize)
      if (previewState.value) return

      previewState.value = 'loading'
      try {
        const data = typeof source === 'function' ? await source() : source
        if (!active) {
          if (typeof data === 'string') releasePreviewStreamUrl(data)
          return
        }
        if (typeof data === 'string') streamUrl = data
        const size =
          typeof data === 'string' ? listedSize : data instanceof Blob ? data.size : data.byteLength
        previewState.value =
          sizeState(
            size,
            limitSize || (streamed && typeof data !== 'string' && !(data instanceof Blob)),
          ) ?? 'loading'
        if (previewState.value !== 'loading') return
        if (parquet) {
          if (data instanceof Blob) {
            contentBlob.value = data
          } else {
            const file =
              typeof data === 'string'
                ? await urlPreviewBytes(data, size, { signal: controller.signal })
                : data
            if (!active) return
            parquetFile.value = file
          }
        } else if (streamed && typeof data === 'string') {
          contentUrl.value = data
        } else {
          const blob =
            typeof data === 'string'
              ? await fetchPreviewBlob(data, controller.signal, limitSize)
              : data instanceof Blob
                ? data
                : new Blob([await data.slice(0, data.byteLength)])
          if (!active) return
          if (!blob || blob.size === 0) {
            previewState.value = blob ? 'empty' : 'too-big'
            return
          }
          const processed = await processFileContent(blob, type)
          const text = processed.text ?? (getFileExtension(name) === 'xml' ? await blob.text() : '')
          ownedUrl = processed.contentUrl
          if (!active) {
            if (ownedUrl) URL.revokeObjectURL(ownedUrl)
            return
          }
          contentUrl.value = ownedUrl ?? ''
          textContent.value = text
          contentBlob.value = blob
        }
        previewState.value = null
      } catch (failure) {
        if (!active) return
        error.value = failure instanceof Error ? failure.message : 'Failed to load file'
        previewState.value = 'error'
      }
    },
    { immediate: true },
  )

  return { fileType, error, contentUrl, textContent, contentBlob, parquetFile, previewState }
}
