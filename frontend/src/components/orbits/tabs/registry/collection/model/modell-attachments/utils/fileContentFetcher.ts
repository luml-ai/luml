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

    const tarBlobUrl = (window as any).__tarBlobUrl
    if (!tarBlobUrl) {
      throw new Error('Tar blob URL not found')
    }

    const tarResponse = await fetch(tarBlobUrl)
    const tarArrayBuffer = await tarResponse.arrayBuffer()
    const tarData = new Uint8Array(tarArrayBuffer)

    const searchStr = file.path
    const encoder = new TextEncoder()
    const searchBytes = encoder.encode(searchStr)

    let tarHeaderOffset = -1
    for (let i = offset; i < offset + 2048 && i < tarData.length - searchBytes.length; i++) {
      let match = true
      for (let j = 0; j < searchBytes.length; j++) {
        if (tarData[i + j] !== searchBytes[j]) {
          match = false
          break
        }
      }
      if (match) {
        tarHeaderOffset = i
        break
      }
    }

    if (tarHeaderOffset === -1) {
      throw new Error('Could not find tar header for file')
    }

    const headerStart = tarHeaderOffset
    const sizeBytes = tarData.slice(headerStart + 124, headerStart + 136)
    const sizeOctalStr = Array.from(sizeBytes)
      .map((b) => String.fromCharCode(b))
      .join('')
      .trim()
      .replace(/\0/g, '')
      .replace(/ /g, '')

    const fileSize = parseInt(sizeOctalStr, 8)

    const dataOffset = headerStart + 512
    const fileData = tarArrayBuffer.slice(dataOffset, dataOffset + fileSize)
    
    const blob = new Blob([fileData])

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

