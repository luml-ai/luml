import type { FileType } from './fileTypes'
import type { FileContentResult } from '../interfaces/interfaces'

type ProcessorResult = Promise<Partial<FileContentResult>>

export async function processImageContent(blob: Blob): ProcessorResult {
  return {
    contentUrl: URL.createObjectURL(blob),
  }
}

export async function processSvgContent(blob: Blob): ProcessorResult {
  const svgText = await blob.text()
  const sanitizedSvg = svgText.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
  const svgBlob = new Blob([sanitizedSvg], { type: 'image/svg+xml' })
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

export async function processTextContent(blob: Blob, fileName: string): ProcessorResult {
  let textContent = await blob.text()
  const ext = fileName.split('.').pop()?.toLowerCase()
  if (ext === 'json') {
    try {
      textContent = JSON.stringify(JSON.parse(textContent), null, 2)
    } catch {}
  }
  return { text: textContent }
}

export async function processHtmlContent(blob: Blob): ProcessorResult {
  let htmlText = await blob.text()
  htmlText = htmlText.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
  htmlText = await convertImagesToBlob(htmlText)
  const htmlBlob = new Blob([htmlText], { type: 'text/html' })
  return {
    contentUrl: URL.createObjectURL(htmlBlob),
  }
}

export async function processFileContent(
  blob: Blob,
  fileType: FileType,
  fileName: string,
): ProcessorResult {
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
      return processTextContent(blob, fileName)
    case 'html':
      return processHtmlContent(blob)
    default:
      return {}
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
      console.warn('Failed to convert image', src, e)
    }
  }

  return doc.documentElement.outerHTML
}
