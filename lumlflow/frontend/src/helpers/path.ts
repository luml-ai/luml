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
