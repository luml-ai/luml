import { toDisplayString } from 'vue'

export const PREVIEW_CHARACTERS = 2_000
/** YAML and Markdown render the whole value into the page, so only smaller values get them. */
export const FORMATTED_VIEW_MAX_BYTES = 1024 * 1024

/** The text Vue shows for the value: strings as they are, objects as indented JSON. */
export function valueText(value: unknown): string {
  return typeof value === 'string' ? value : toDisplayString(value)
}

export function isLargeText(text: string): boolean {
  return text.length > PREVIEW_CHARACTERS
}

/** The first PREVIEW_CHARACTERS code units, without splitting a surrogate pair at the end. */
export function previewText(text: string): string {
  if (!isLargeText(text)) return text
  const lastKept = text.charCodeAt(PREVIEW_CHARACTERS - 1)
  const end = lastKept >= 0xd800 && lastKept <= 0xdbff ? PREVIEW_CHARACTERS - 1 : PREVIEW_CHARACTERS
  return text.slice(0, end)
}

export function utf8ByteLength(text: string): number {
  let bytes = 0
  for (let index = 0; index < text.length; index++) {
    const code = text.charCodeAt(index)
    if (code < 0x80) bytes += 1
    else if (code < 0x800) bytes += 2
    else if (code >= 0xd800 && code <= 0xdbff && index + 1 < text.length) {
      // A surrogate pair is one 4-byte character.
      bytes += 4
      index++
    } else bytes += 3
  }
  return bytes
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let size = bytes / 1024
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit++
  }
  return `${size.toFixed(1)} ${units[unit]}`
}

export function previewLine(bytes: number): string {
  return `First ${PREVIEW_CHARACTERS.toLocaleString('en-US')} characters of ${formatBytes(bytes)}.`
}

export function valueFileName(title: string, value: unknown): string {
  const base = title.replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'value'
  return `${base}.${typeof value === 'string' ? 'txt' : 'json'}`
}
