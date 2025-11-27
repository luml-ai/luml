import { getFileType } from '@/components/orbits/tabs/registry/collection/model/modell-attachments/utils/fileTypes'
import { processFileContent } from '@/components/orbits/tabs/registry/collection/model/modell-attachments/utils/fileContentProcessors'
import type {
  FetchFileContentParams,
  FileContentResult,
} from '@/components/orbits/tabs/registry/collection/model/modell-attachments/attachments.interfaces'

const MAX_PREVIEW_SIZE = 10 * 1024 * 1024

export async function fetchFileContent(params: FetchFileContentParams): Promise<FileContentResult> {
  const { file, fileIndex, downloadUrl } = params
  if (!file.path || file.type !== 'file') {
    return {}
  }

  const fileType = getFileType(file.name)
  if (!fileType) {
    return { error: 'unsupported' }
  }
  try {
    const rangeData = fileIndex[file.path]
    if (!rangeData) {
      return { error: 'not-found' }
    }
    const [offset, length] = rangeData
    if (length === 0) {
      return { error: 'empty' }
    }
    if (length > MAX_PREVIEW_SIZE) {
      return { error: 'too-big' }
    }
    const blob = await fetchFileBlob(downloadUrl, offset, length)
    const processed = await processFileContent(blob, fileType, file.name)
    return {
      blob,
      text: processed.text,
      contentUrl: processed.contentUrl,
    }
  } catch (e) {
    console.error('Failed to fetch file content:', e)
    return { error: 'unknown' }
  }
}

async function fetchFileBlob(url: string, offset: number, length: number): Promise<Blob> {
  const end = offset + length - 1
  const response = await fetch(url, {
    headers: { Range: `bytes=${offset}-${end}` },
  })

  if (!response.ok) {
    throw new Error(`HTTP Error: ${response.status}`)
  }

  return response.blob()
}
