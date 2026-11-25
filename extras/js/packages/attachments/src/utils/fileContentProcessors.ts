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

// A byte order mark, then comments and white space, then the doctype.
const LEADING_DOCTYPE = /^(?:\xef\xbb\xbf)?(?:\s|<!--[\s\S]*?-->)*<!doctype[^>]*>/i

/**
 * Where the policy goes: after a leading doctype, which must stay first for the document to
 * render in standards mode, and before any content that could load a resource.
 */
async function policyOffset(blob: Blob): Promise<number> {
  // Byte by byte as Latin-1: the offset is in bytes and the document's own encoding is kept.
  const head = new Uint8Array(await blob.slice(0, 64 * 1024).arrayBuffer())
  const text = Array.from(head, (byte) => String.fromCharCode(byte)).join('')
  return LEADING_DOCTYPE.exec(text)?.[0].length ?? 0
}

export async function processHtmlContent(blob: Blob): ProcessorResult {
  // The source is untrusted and can contain subresources pointing outside the project.
  const policy =
    "default-src 'none'; img-src data: blob:; media-src data: blob:; font-src data: blob:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
  const offset = await policyOffset(blob)
  const htmlBlob = new Blob(
    [
      blob.slice(0, offset),
      `<meta http-equiv="Content-Security-Policy" content="${policy}">`,
      blob.slice(offset),
    ],
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
