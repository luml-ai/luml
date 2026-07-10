import { dump } from 'js-yaml'

export function isYamlLike(text: string) {
  const trimmed = text.trim()
  if (!trimmed) return false
  if (tryParseJson(text) !== null) return true
  const hasKeyColon = /^[ \t-]*[A-Za-z_][A-Za-z0-9_-]*:\s+\S+/m.test(trimmed)
  const hasMultilineHyphen = /^\s*-\s+/m.test(trimmed)
  const hasYamlStart = /^---\s*$/m.test(trimmed)
  return hasKeyColon || hasMultilineHyphen || hasYamlStart
}

export function jsonToYaml(obj: any, indent = 2, lineWidth = 160): string {
  return dump(obj, { indent, lineWidth })
}

export function tryParseJson(text: string) {
  try {
    const trimmed = text.trim()
    if (!trimmed) return null
    return JSON.parse(trimmed)
  } catch {
    return null
  }
}

export function valueToString(value: any): string | null {
  if (value === null || value === undefined) return null
  if (value === true) return 'true'
  if (value === false) return 'false'
  if (typeof value === 'string') return value
  if (typeof value === 'number') return value.toString()
  if (Array.isArray(value)) {
    return value.map((item) => valueToString(item)).join(', ')
  }
  if (typeof value === 'object') {
    return jsonToYaml(value)
  }
  return String(value)
}
