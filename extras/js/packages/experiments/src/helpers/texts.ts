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

function isMarkedObject(value: unknown, marker: string): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as Record<string, unknown>)[marker] === true
  )
}

/** A boolean expectation has counts and no value: the text its table cell shows. */
function booleanCountsText(cell: Record<string, unknown>): string | null {
  const parts = [
    [cell.positive, 'True'],
    [cell.negative, 'False'],
  ].flatMap(([count, title]) => (count ? [`${title} (${count})`] : []))
  return parts.length ? parts.join(' ') : null
}

/**
 * Annotation columns hold objects for their table cells: a feedback column is exported as its
 * counts and an expectation column as its expected value, or its counts when it has none. The
 * counts do not start with "+" or "-", which spreadsheets read as a formula.
 */
export function tableCellToString(value: unknown): string | null {
  if (isMarkedObject(value, 'isFeedbackColumn')) {
    return `${value.positiveCount} positive, ${value.negativeCount} negative`
  }
  if (isMarkedObject(value, 'isExpectationColumn')) {
    if (value.value === null || value.value === undefined) return booleanCountsText(value)
    return valueToString(value.value)
  }
  return valueToString(value)
}
