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

const BYTE_ORDER_MARK = '\xef\xbb\xbf'
// What the HTML parser skips before a doctype. `\s` also matches characters it keeps as text.
const WHITE_SPACE = new Set(['\t', '\n', '\f', '\r', ' '])
// Every doctype state of the tokenizer ends the token at the first `>`, quoted or not.
const DOCTYPE = /<!doctype[^>]*>/iy

/**
 * The end of a doctype that follows a byte order mark, comments and white space, or 0.
 * A single pass, so a document opening with many comments cannot stall the preview.
 *
 * The policy only applies from `<head>`, so any doubt about where the browser ends a comment
 * gives 0: a policy placed first is always read into `<head>`.
 */
export function leadingDoctypeEnd(text: string): number {
  let position = text.startsWith(BYTE_ORDER_MARK) ? BYTE_ORDER_MARK.length : 0
  while (position < text.length) {
    if (WHITE_SPACE.has(text[position]!)) {
      position++
    } else if (text.startsWith('<!--', position)) {
      const body = position + 4
      // Browsers also end a comment at `<!-->`, `<!--->` and `--!>`.
      if (text.startsWith('>', body) || text.startsWith('->', body)) return 0
      const end = text.indexOf('-->', body)
      if (end < 0 || text.slice(body, end).includes('--!>')) return 0
      position = end + 3
    } else {
      break
    }
  }
  DOCTYPE.lastIndex = position
  if (!DOCTYPE.exec(text)) return 0
  const end = DOCTYPE.lastIndex
  // A control character, such as the escape that switches ISO-2022-JP into two-byte text,
  // can make the browser decode these bytes into something other than what was scanned.
  for (let index = 0; index < end; index++) {
    if (text.charCodeAt(index) < 0x20 && !WHITE_SPACE.has(text[index]!)) return 0
  }
  return end
}

/**
 * Where the policy goes: after a leading doctype, which must stay first for the document to
 * render in standards mode, and before any content that could load a resource.
 */
async function policyOffset(blob: Blob): Promise<number> {
  // Byte by byte as Latin-1: the offset is in bytes and the document's own encoding is kept.
  const head = new Uint8Array(await blob.slice(0, 64 * 1024).arrayBuffer())
  const text = Array.from(head, (byte) => String.fromCharCode(byte)).join('')
  return leadingDoctypeEnd(text)
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
