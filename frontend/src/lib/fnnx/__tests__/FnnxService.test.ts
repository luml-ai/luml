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

describe('FnnxService.hasAttachments', () => {
  const archivePath =
    'meta_artifacts/dataforce.studio~c~~c~experiment_snapshot~c~v1~~et~~abc123/attachments.tar'
  const indexPath =
    'meta_artifacts/dataforce.studio~c~~c~experiment_snapshot~c~v1~~et~~abc123/attachments.index.json'

  it('returns true when the attachments index contains files', () => {
    const fileIndex: FileIndex = {
      [archivePath]: [0, 10240],
      [indexPath]: [10240, 42],
    }

    expect(FnnxService.hasAttachments(fileIndex)).toBe(true)
  })

  it('returns false when the attachments index is empty', () => {
    const fileIndex: FileIndex = {
      [archivePath]: [0, 10240],
      [indexPath]: [10240, 2],
    }

    expect(FnnxService.hasAttachments(fileIndex)).toBe(false)
  })

  it('returns false when the archive or index is missing', () => {
    expect(FnnxService.hasAttachments({ [archivePath]: [0, 10240] })).toBe(false)
    expect(FnnxService.hasAttachments({ [indexPath]: [0, 42] })).toBe(false)
  })
})
