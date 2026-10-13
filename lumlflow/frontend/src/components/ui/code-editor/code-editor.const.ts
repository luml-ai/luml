import type { CodeEditorHandle, CodeEditorOptions } from './code-editor.interface'
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
  temporarilySetTabFocusMode,
} from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import {
  bracketMatching,
  HighlightStyle,
  indentUnit,
  syntaxHighlighting,
} from '@codemirror/language'
import { Compartment, EditorState, type Extension } from '@codemirror/state'
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view'
import { tags } from '@lezer/highlight'

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
  const mode = new Compartment()

  const view = new EditorView({
    parent: options.parent,
    state: EditorState.create({
      doc: options.doc,
      extensions: [
        lineNumbers(),
        history(),
        bracketMatching(),
        indentUnit.of('    '),
        python(),
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
          if (update.docChanged) options.onChange(update.state.doc.toString())
        }),
      ],
    }),
  })

  return {
    view,
    setSource(source: string): void {
      if (view.state.doc.toString() === source) return
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: source } })
    },
    setReadonly(readonly: boolean): void {
      view.dispatch({ effects: mode.reconfigure(modeExtension(readonly)) })
    },
    destroy(): void {
      view.destroy()
    },
  }
}
