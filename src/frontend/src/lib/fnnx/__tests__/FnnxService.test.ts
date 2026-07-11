import { describe, it, expect, vi } from 'vitest'

vi.mock('@fnnx-ai/web', () => ({ Model: class {} }))
vi.mock('@fnnx-ai/common/dist/interfaces', () => ({}))
vi.mock('@/helpers/helpers', () => ({
  fixNumber: vi.fn(),
  getFormattedMetric: vi.fn(),
  toPercent: vi.fn(),
}))

import { FnnxService } from '../FnnxService'
import type { FileIndex } from '@/lib/api/artifacts/interfaces'

describe('FnnxService.findHtmlCard', () => {
  it('returns the key for a dataset_card.zip path', () => {
    const datasetCardPath =
      'meta_artifacts/dataforce.studio~c~~c~dataset_card~c~v1~~et~~abc123/dataset_card.zip'
    const fileIndex: FileIndex = {
      [datasetCardPath]: [0, 100],
    }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe(datasetCardPath)
  })

  it('returns the key for a model_card.zip path (no regression)', () => {
    const modelCardPath =
      'meta_artifacts/dataforce.studio~c~~c~model_card~c~v1~~et~~abc123/model_card.zip'
    const fileIndex: FileIndex = {
      [modelCardPath]: [0, 100],
    }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe(modelCardPath)
  })

  it('returns undefined when file_index has no matching entry', () => {
    const fileIndex: FileIndex = {
      'some/other/file.txt': [0, 50],
      'meta.json': [50, 100],
    }
    expect(FnnxService.findHtmlCard(fileIndex)).toBeUndefined()
  })

  it('returns the key for a legacy card.zip path', () => {
    const fileIndex: FileIndex = {
      'card.zip': [0, 100],
    }
    expect(FnnxService.findHtmlCard(fileIndex)).toBe('card.zip')
  })
})
