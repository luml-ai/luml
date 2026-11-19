import { EditorState } from '@codemirror/state'
import { language } from '@codemirror/language'
import { describe, expect, it } from 'vitest'
import {
  EXTENSION_LANGUAGES,
  getFileExtension,
  getFileType,
  getPreviewLanguage,
} from '../fileTypes'
import { languageExtension } from '../codeHighlighting'

describe('shared attachment file types', () => {
  it.each([
    ['image', ['gif', 'webp']],
    ['code', ['toml', 'ini', 'cfg', 'sh', 'sql', 'jsx', 'tsx', 'css']],
    ['text', ['log', 'txt', 'md', 'json']],
    ['table', ['arrow', 'parquet', 'csv', 'xml']],
    ['html', ['html']],
  ] as const)('detects %s files by extension, case-insensitively', (type, extensions) => {
    for (const ext of extensions) expect(getFileType(`file.${ext.toUpperCase()}`)).toBe(type)
  })

  it.each(Object.entries(EXTENSION_LANGUAGES))(
    'loads the mapped CodeMirror language for .%s',
    (ext, expected) => {
      expect(getPreviewLanguage(`file.${ext.toUpperCase()}`)).toBe(expected)
      const state = EditorState.create({ extensions: [languageExtension(expected)] })
      expect(state.facet(language)).toBeTruthy()
    },
  )

  it('leaves plain text and unknown extensions without a language', () => {
    for (const name of ['run.log', 'notes.txt', 'x.constructor', 'LICENSE']) {
      expect(getPreviewLanguage(name)).toBeUndefined()
    }
    expect(getFileType('file.unknown')).toBeNull()
  })

  it('uses the final extension of the basename, including in provider paths', () => {
    for (const name of ['py', '.json', 'docs.v2/json', 'docs.v2/.py', 'cfg.', 'folder.json/']) {
      expect(getFileExtension(name)).toBe('')
      expect(getFileType(name)).toBeNull()
      expect(getPreviewLanguage(name)).toBeUndefined()
    }
    expect(getFileType('runs.v1/.hidden.data.PARQUET')).toBe('table')
    expect(getPreviewLanguage('configs.v1\\nested\\.params.YAML')).toBe('yaml')
  })
})
