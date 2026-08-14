/**
 * CodeMirror 6, configured for cell source and kept behind a dynamic import.
 *
 * Nothing here rides in the workbench's first chunk: a card showing read-only
 * source never fetches it, and the editor's cost is paid by the edit gesture
 * that asked for it.
 *
 * Every colour is a CSS variable rather than a literal. `SourceEditor.vue`
 * defines both palettes off the app's theme tokens, so light and dark stay one
 * stylesheet instead of two editor themes that have to be kept in step.
 */

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

const houseTheme = EditorView.theme({
  '&': {
    color: 'var(--flow-code-fg)',
    backgroundColor: 'var(--flow-code-bg)',
    border: '1px solid var(--flow-code-border)',
    borderRadius: '0.375rem',
    fontSize: '0.875rem',
  },
  '&.cm-focused': { outline: 'none', borderColor: 'var(--flow-code-accent)' },
  '.cm-scroller': {
    fontFamily: 'var(--flow-code-font)',
    lineHeight: '1.625',
    maxHeight: 'var(--flow-code-max-height)',
    overflow: 'auto',
  },
  '.cm-content': { padding: '0.5rem 0', caretColor: 'var(--flow-code-accent)' },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    color: 'var(--flow-code-gutter)',
    border: 'none',
  },
  '.cm-lineNumbers .cm-gutterElement': { padding: '0 0.5rem 0 0.75rem' },
  '.cm-activeLine': { backgroundColor: 'var(--flow-code-active)' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--flow-code-fg)' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--flow-code-accent)' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: 'var(--flow-code-selection)',
  },
  '.cm-matchingBracket, &.cm-focused .cm-matchingBracket': {
    backgroundColor: 'var(--flow-code-bracket)',
    outline: 'none',
  },
  '.cm-nonmatchingBracket': { color: 'var(--flow-code-invalid)' },
})

const housePython = HighlightStyle.define([
  {
    tag: [tags.keyword, tags.controlKeyword, tags.moduleKeyword],
    color: 'var(--flow-code-keyword)',
  },
  { tag: [tags.definitionKeyword, tags.operatorKeyword], color: 'var(--flow-code-keyword)' },
  {
    tag: [tags.string, tags.special(tags.string), tags.docString],
    color: 'var(--flow-code-string)',
  },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--flow-code-number)' },
  { tag: [tags.comment, tags.lineComment], color: 'var(--flow-code-comment)', fontStyle: 'italic' },
  {
    tag: [tags.function(tags.variableName), tags.function(tags.propertyName)],
    color: 'var(--flow-code-function)',
  },
  {
    tag: [tags.definition(tags.variableName), tags.definition(tags.propertyName)],
    color: 'var(--flow-code-function)',
  },
  { tag: [tags.className, tags.typeName, tags.namespace], color: 'var(--flow-code-type)' },
  {
    tag: [tags.self, tags.atom, tags.standard(tags.variableName)],
    color: 'var(--flow-code-builtin)',
  },
  { tag: [tags.propertyName, tags.attributeName], color: 'var(--flow-code-property)' },
  { tag: [tags.operator, tags.punctuation, tags.bracket], color: 'var(--flow-code-punct)' },
  { tag: tags.meta, color: 'var(--flow-code-meta)' },
  { tag: tags.invalid, color: 'var(--flow-code-invalid)' },
])

/** What a locked surface drops: the caret, and the accents that imply one. */
function modeExtension(readonly: boolean): Extension {
  return readonly
    ? [EditorState.readOnly.of(true), EditorView.editable.of(false)]
    : [highlightActiveLine(), highlightActiveLineGutter()]
}

export interface CodeEditorHandle {
  view: EditorView
  setSource(source: string): void
  setReadonly(readonly: boolean): void
  destroy(): void
}

export interface CodeEditorOptions {
  parent: HTMLElement
  doc: string
  readonly: boolean
  ariaLabel: string
  onChange: (source: string) => void
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
        // Python's own unit, so Tab and the newline auto-indent agree with the
        // file the edit is projected back into.
        indentUnit.of('    '),
        python(),
        syntaxHighlighting(housePython),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          indentWithTab,
          // Tab indents, which traps keyboard navigation inside the editor.
          // Escape is CodeMirror's documented way back out: it hands Tab to the
          // browser again for long enough to leave.
          { key: 'Escape', run: temporarilySetTabFocusMode },
        ]),
        EditorView.contentAttributes.of({ 'aria-label': options.ariaLabel }),
        houseTheme,
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
