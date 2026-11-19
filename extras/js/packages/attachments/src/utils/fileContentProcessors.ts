import type { FileType } from './fileTypes'
import type { FileContentResult } from '../interfaces/interfaces'

type ProcessorResult = Promise<Partial<FileContentResult>>

export async function processImageContent(blob: Blob): ProcessorResult {
  return {
    contentUrl: URL.createObjectURL(blob),
  }
}

export async function processSvgContent(blob: Blob): ProcessorResult {
  // svg previews use an image context that disables scripting.
  const svgBlob = new Blob([blob], { type: 'image/svg+xml' })
  return {
    contentUrl: URL.createObjectURL(svgBlob),
  }
}

export async function processMediaContent(blob: Blob): ProcessorResult {
  return {
    contentUrl: URL.createObjectURL(blob),
  }
}

export async function processPdfContent(blob: Blob): ProcessorResult {
  const pdfBlob = new Blob([blob], { type: 'application/pdf' })
  return {
    contentUrl: URL.createObjectURL(pdfBlob),
  }
}

export async function processHtmlContent(blob: Blob): ProcessorResult {
  // The source is untrusted and can contain subresources pointing outside the project.
  const policy =
    "default-src 'none'; img-src data: blob:; media-src data: blob:; font-src data: blob:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
  const htmlBlob = new Blob(
    [`<meta http-equiv="Content-Security-Policy" content="${policy}">`, blob],
    { type: 'text/html' },
  )
  return {
    contentUrl: URL.createObjectURL(htmlBlob),
    text: await blob.text(),
  }
}

export async function processFileContent(blob: Blob, fileType: FileType): ProcessorResult {
  switch (fileType) {
    case 'image':
      return processImageContent(blob)
    case 'svg':
      return processSvgContent(blob)
    case 'audio':
    case 'video':
      return processMediaContent(blob)
    case 'pdf':
      return processPdfContent(blob)
    case 'text':
    case 'code':
      return { text: await blob.text() }
    case 'html':
      return processHtmlContent(blob)
    default:
      return {}
  }
}
