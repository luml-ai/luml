import type { CodeEditorHandle, CodeEditorOptions } from './code-editor.interface'
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
  temporarilySetTabFocusMode,
} from '@codemirror/commands'
import { languageExtension, type PreviewLanguage } from '@luml/attachments'
import {
  bracketMatching,
  HighlightStyle,
  indentUnit,
  syntaxHighlighting,
} from '@codemirror/language'
import { Annotation, Compartment, EditorState, type Extension } from '@codemirror/state'
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view'
import { tags } from '@lezer/highlight'

const externalSource = Annotation.define<boolean>()

const theme = EditorView.theme({
  '&': {
    color: 'var(--ui-code-fg)',
    backgroundColor: 'var(--ui-code-bg)',
    border: '1px solid var(--ui-code-border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  },
  '&.cm-focused': { outline: 'none', borderColor: 'var(--ui-code-accent)' },
  '.cm-scroller': {
    fontFamily: 'var(--ui-code-font)',
    lineHeight: '1.625',
    maxHeight: 'var(--ui-code-max-height)',
    overflow: 'auto',
  },
  '.cm-content': {
    padding: '0.5rem 0',
    caretColor: 'var(--ui-code-accent)',
    cursor: 'text',
  },
  '.cm-gutters': {
    backgroundColor: 'var(--ui-code-bg)',
    color: 'var(--ui-code-gutter)',
    border: 'none',
  },
  '.cm-lineNumbers .cm-gutterElement': { padding: '0 0.5rem 0 0.75rem' },
  '.cm-activeLine': { backgroundColor: 'var(--ui-code-active)' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--ui-code-fg)' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--ui-code-accent)' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: 'var(--ui-code-selection)',
  },
  '.cm-matchingBracket, &.cm-focused .cm-matchingBracket': {
    backgroundColor: 'var(--ui-code-bracket)',
    outline: 'none',
  },
  '.cm-nonmatchingBracket': { color: 'var(--ui-code-invalid)' },
})

const highlightStyle = HighlightStyle.define([
  {
    tag: [tags.keyword, tags.controlKeyword, tags.moduleKeyword],
    color: 'var(--ui-code-keyword)',
  },
  { tag: [tags.definitionKeyword, tags.operatorKeyword], color: 'var(--ui-code-keyword)' },
  {
    tag: [tags.string, tags.special(tags.string), tags.docString],
    color: 'var(--ui-code-string)',
  },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--ui-code-number)' },
  {
    tag: [tags.comment, tags.lineComment],
    color: 'var(--ui-code-comment)',
    fontStyle: 'italic',
  },
  {
    tag: [tags.function(tags.variableName), tags.function(tags.propertyName)],
    color: 'var(--ui-code-function)',
  },
  {
    tag: [tags.definition(tags.variableName), tags.definition(tags.propertyName)],
    color: 'var(--ui-code-function)',
  },
  { tag: [tags.className, tags.typeName, tags.namespace], color: 'var(--ui-code-type)' },
  {
    tag: [tags.self, tags.atom, tags.standard(tags.variableName)],
    color: 'var(--ui-code-builtin)',
  },
  { tag: [tags.propertyName, tags.attributeName], color: 'var(--ui-code-property)' },
  { tag: [tags.operator, tags.punctuation, tags.bracket], color: 'var(--ui-code-punct)' },
  { tag: tags.meta, color: 'var(--ui-code-meta)' },
  { tag: tags.invalid, color: 'var(--ui-code-invalid)' },
])

function modeExtension(readonly: boolean): Extension {
  return readonly
    ? [EditorState.readOnly.of(true), EditorView.editable.of(false)]
    : [highlightActiveLine(), highlightActiveLineGutter()]
}

export function mountCodeEditor(options: CodeEditorOptions): CodeEditorHandle {
  // CodeMirror uses one document position per line break. Keep the original
  // separators for unchanged spans, including files with mixed line endings.
  let source = options.doc
  let endings: string[] = source.match(/\r\n|\r|\n/g) ?? []
  let lineBreak = endings[0] ?? '\n'
  const mode = new Compartment()
  const syntax = new Compartment()
  const initialLanguage = options.language === undefined ? 'python' : options.language

  const view = new EditorView({
    parent: options.parent,
    state: EditorState.create({
      doc: options.doc,
      extensions: [
        lineNumbers(),
        history(),
        bracketMatching(),
        indentUnit.of('    '),
        syntax.of(initialLanguage ? languageExtension(initialLanguage) : []),
        syntaxHighlighting(highlightStyle),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          indentWithTab,
          { key: 'Escape', run: temporarilySetTabFocusMode },
        ]),
        EditorView.contentAttributes.of({ 'aria-label': options.ariaLabel }),
        theme,
        mode.of(modeExtension(options.readonly)),
        EditorView.updateListener.of((update) => {
          if (!update.docChanged || update.transactions.some((tr) => tr.annotation(externalSource)))
            return
          const doc = update.state.doc
          const nextEndings: string[] = Array(doc.lines - 1).fill(lineBreak)
          update.changes.iterGaps((oldStart, newStart, length) => {
            const oldDoc = update.startState.doc
            const first = oldDoc.lineAt(oldStart).number
            const end = oldDoc.lineAt(oldStart + length).number
            const dest = doc.lineAt(newStart).number
            for (let line = first; line < end; line++) {
              nextEndings[dest + line - first - 1] = endings[line - 1]!
            }
          })
          endings = nextEndings
          const lines = doc.toJSON()
          source = lines.map((line, i) => line + (endings[i] ?? '')).join('')
          options.onChange(source)
        }),
      ],
    }),
  })

  return {
    view,
    setSource(next: string): void {
      if (source === next) return
      // This replacement comes from the model, including its own separators.
      source = next
      endings = next.match(/\r\n|\r|\n/g) ?? []
      lineBreak = endings[0] ?? '\n'
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: next },
        annotations: externalSource.of(true),
      })
    },
    setReadonly(readonly: boolean): void {
      view.dispatch({ effects: mode.reconfigure(modeExtension(readonly)) })
    },
    setLanguage(language: PreviewLanguage | null): void {
      view.dispatch({ effects: syntax.reconfigure(language ? languageExtension(language) : []) })
    },
    destroy(): void {
      view.destroy()
    },
  }
}
