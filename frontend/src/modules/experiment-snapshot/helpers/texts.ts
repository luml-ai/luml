export function isYamlLike(text: string) {
  const trimmed = text.trim()
  if (!trimmed) return false
  if (tryParseJson(text) !== null) return true
  const hasKeyColon = /^[ \t-]*[A-Za-z_][A-Za-z0-9_-]*:\s+\S+/m.test(trimmed)
  const hasMultilineHyphen = /^\s*-\s+/m.test(trimmed)
  const hasYamlStart = /^---\s*$/m.test(trimmed)
  return hasKeyColon || hasMultilineHyphen || hasYamlStart
}

export function jsonToYaml(obj: any, indent = 0): string {
  const spaces = '  '.repeat(indent)
  if (Array.isArray(obj)) {
    return obj.map((v) => `${spaces}- ${jsonToYaml(v, indent + 1).trimStart()}`).join('\n')
  } else if (obj && typeof obj === 'object') {
    return Object.entries(obj)
      .map(([k, v]) => `${spaces}${k}: ${jsonToYaml(v, indent + 1).trimStart()}`)
      .join('\n')
  }
  return String(obj)
}

function tryParseJson(text: string) {
  try {
    const trimmed = text.trim()
    if (!trimmed) return null
    return JSON.parse(trimmed)
  } catch (e) {
    return null
  }
}
