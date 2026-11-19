import { parseAllDocuments, visit as visitYaml } from 'yaml'
import { format } from 'jsonc-parser'
import { COLLECTION_STYLE, CORE_SCHEMA, eventsToAst, parseEvents, present, visit } from 'js-yaml'

export function prettySource(source: string, language: 'json' | 'yaml'): string {
  if (language === 'json') {
    // Validate strict JSON, then format the original tokens to preserve numeric precision.
    JSON.parse(source)
    const edits = format(source, undefined, { insertSpaces: true, tabSize: 2 })
    const parts: string[] = []
    let offset = 0
    for (const edit of edits) {
      parts.push(source.slice(offset, edit.offset), edit.content)
      offset = edit.offset + edit.length
    }
    parts.push(source.slice(offset))
    return parts.join('')
  }

  const events = parseEvents(source, {})
  const options = { source, schema: CORE_SCHEMA }
  // Validate keys and alias references. Format the syntax tree to preserve scalar values.
  for (const document of parseAllDocuments(source, { intAsBigInt: true })) {
    if (document.errors.length) throw document.errors[0]
    visitYaml(document, {
      Alias(_, alias) {
        if (!alias.resolve(document)) throw new Error('Unknown YAML alias')
      },
    })
  }
  const documents = eventsToAst(events, options)
  visit(documents, (node) => {
    if (node.kind === 'mapping' || node.kind === 'sequence') node.style = COLLECTION_STYLE.BLOCK
  })
  return present(documents, options)
}
