import { describe, it, expect, vi } from 'vitest'

vi.mock('@fnnx-ai/web', () => ({ Model: class {} }))
vi.mock('@fnnx-ai/common/dist/interfaces', () => ({}))

import { FnnxService } from './FnnxService'
import type { FileIndex } from '../api/artifacts/interfaces'

describe('FnnxService.findHtmlCard', () => {
  it('returns the key for a dataset_card.zip path', () => {
    const key =
      'meta_artifacts/dataforce.studio~c~~c~dataset_card~c~v1~~et~~abc123/dataset_card.zip'
    const fileIndex: FileIndex = { [key]: [0, 100] }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe(key)
  })

  it('returns the key for a model_card.zip path (no regression)', () => {
    const key =
      'meta_artifacts/dataforce.studio~c~~c~model_card~c~v1~~et~~abc123/model_card.zip'
    const fileIndex: FileIndex = { [key]: [0, 100] }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe(key)
  })

  it('returns the key for a bare card.zip path', () => {
    const fileIndex: FileIndex = { 'card.zip': [0, 100] }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe('card.zip')
  })

  it('returns undefined when file_index has no matching entry', () => {
    const fileIndex: FileIndex = { 'model.bin': [0, 500] }
    expect(FnnxService.findHtmlCard(fileIndex)).toBeUndefined()
  })
})
