import type { EditorView } from '@codemirror/view'

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
