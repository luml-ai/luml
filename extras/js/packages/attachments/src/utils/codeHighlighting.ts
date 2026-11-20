import { css } from '@codemirror/lang-css'
import { html } from '@codemirror/lang-html'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { python } from '@codemirror/lang-python'
import { sql } from '@codemirror/lang-sql'
import { xml } from '@codemirror/lang-xml'
import { yaml } from '@codemirror/lang-yaml'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import type { Extension } from '@codemirror/state'
import { tags } from '@lezer/highlight'
import type { PreviewLanguage } from './fileTypes'

const languages = {
  css,
  html,
  javascript,
  jsx: () => javascript({ jsx: true }),
  typescript: () => javascript({ typescript: true }),
  tsx: () => javascript({ jsx: true, typescript: true }),
  json,
  markdown,
  python,
  sql,
  xml,
  yaml,
} satisfies Record<PreviewLanguage, () => Extension>

export function languageExtension(language: PreviewLanguage): Extension {
  return languages[language]()
}

// Match Flow's code editor palette, including tags used by markup languages.
export const previewHighlighting = syntaxHighlighting(
  HighlightStyle.define([
    { tag: tags.keyword, color: 'var(--ui-code-keyword)' },
    { tag: [tags.string, tags.docString], color: 'var(--ui-code-string)' },
    { tag: [tags.number, tags.bool, tags.null], color: 'var(--ui-code-number)' },
    { tag: tags.comment, color: 'var(--ui-code-comment)', fontStyle: 'italic' },
    {
      tag: [
        tags.function(tags.variableName),
        tags.function(tags.propertyName),
        tags.definition(tags.variableName),
        tags.definition(tags.propertyName),
      ],
      color: 'var(--ui-code-function)',
    },
    {
      tag: [tags.className, tags.typeName, tags.namespace, tags.tagName],
      color: 'var(--ui-code-type)',
    },
    {
      tag: [tags.self, tags.atom, tags.standard(tags.variableName)],
      color: 'var(--ui-code-builtin)',
    },
    { tag: [tags.propertyName, tags.attributeName], color: 'var(--ui-code-property)' },
    { tag: [tags.operator, tags.punctuation, tags.bracket], color: 'var(--ui-code-punct)' },
    { tag: tags.meta, color: 'var(--ui-code-meta)' },
    { tag: tags.heading, color: 'var(--ui-code-keyword)', fontWeight: 'bold' },
    { tag: tags.link, color: 'var(--ui-code-function)', textDecoration: 'underline' },
    { tag: tags.emphasis, fontStyle: 'italic' },
    { tag: tags.strong, fontWeight: 'bold' },
    { tag: tags.invalid, color: 'var(--ui-code-invalid)' },
  ]),
)
