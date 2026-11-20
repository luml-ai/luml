import type { EditorView } from '@codemirror/view'
import type { PreviewLanguage } from '@luml/attachments'

export interface CodeEditorHandle {
  view: EditorView
  setSource(source: string): void
  setReadonly(readonly: boolean): void
  setLanguage(language: PreviewLanguage | null): void
  destroy(): void
}

export interface CodeEditorOptions {
  parent: HTMLElement
  doc: string
  readonly: boolean
  language?: PreviewLanguage | null
  ariaLabel: string
  onChange: (source: string) => void
}
