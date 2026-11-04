const TRAILING_SEPARATORS = /[\\/]+$/
const DRIVE = /^[A-Za-z]:$/

function lastSeparatorIndex(path: string): number {
  return Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'))
}

export function parentDirectory(path: string): string | null {
  const trimmed = path.replace(TRAILING_SEPARATORS, '')
  const lastSeparator = lastSeparatorIndex(trimmed)
  if (lastSeparator < 0) return null
  const parent = trimmed.slice(0, lastSeparator)
  if (parent === '') return trimmed[0]
  if (DRIVE.test(parent)) return `${parent}${trimmed[lastSeparator]}`
  return parent
}

export function baseName(path: string): string {
  const trimmed = path.replace(TRAILING_SEPARATORS, '')
  return trimmed.slice(lastSeparatorIndex(trimmed) + 1)
}

export interface PathSegment {
  name: string
  path: string
}

// The path split into its directories, each carrying the path up to itself.
// A leading separator or a drive letter is folded into the first segment.
export function pathSegments(path: string): PathSegment[] {
  const trimmed = path.replace(TRAILING_SEPARATORS, '')
  if (trimmed === '') return []
  const separator = trimmed.includes('/') ? '/' : '\\'
  const parts = trimmed.split(/[\\/]/)
  const segments: PathSegment[] = []
  let prefix = ''
  for (const [index, part] of parts.entries()) {
    if (part === '') {
      if (index === 0) prefix = separator
      continue
    }
    const first = segments.length === 0
    const current = first ? `${prefix}${part}` : `${prefix}${separator}${part}`
    segments.push({ name: part, path: first && DRIVE.test(part) ? `${part}${separator}` : current })
    prefix = current
  }
  return segments
}
