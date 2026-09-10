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
  it('returns true when the attachments index contains files', () => {
    const fileIndex: FileIndex = {
      'attachments/report.pdf': [0, 42],
    }

    expect(FnnxService.hasAttachments(fileIndex)).toBe(true)
  })

  it('returns false when the attachments index is empty', () => {
    expect(FnnxService.hasAttachments({})).toBe(false)
  })

  it('ignores directory entries', () => {
    expect(FnnxService.hasAttachments({ 'attachments/': [0, 512] })).toBe(false)
  })

  it('ignores zero-byte files', () => {
    expect(FnnxService.hasAttachments({ 'attachments/empty.txt': [0, 0] })).toBe(false)
  })

  it('returns true when usable files appear beside ignored entries', () => {
    const fileIndex: FileIndex = {
      'attachments/': [0, 512],
      'attachments/empty.txt': [512, 0],
      'attachments/report.pdf': [512, 42],
    }

    expect(FnnxService.hasAttachments(fileIndex)).toBe(true)
  })
})

describe('FnnxService.isValidAttachmentsIndex', () => {
  it('accepts file ranges contained by the attachment archive', () => {
    expect(
      FnnxService.isValidAttachmentsIndex(
        {
          'attachments/': [0, 0],
          'attachments/report.pdf': [512, 42],
        },
        1024,
      ),
    ).toBe(true)
  })

  it.each([
    null,
    [],
    { 'attachments/report.pdf': null },
    { 'attachments/report.pdf': [-1, 42] },
    { 'attachments/report.pdf': [0, -1] },
    { 'attachments/report.pdf': [900, 200] },
    { 'attachments/report.pdf': ['0', 42] },
  ])('rejects malformed or out-of-bounds index content', (value) => {
    expect(FnnxService.isValidAttachmentsIndex(value, 1024)).toBe(false)
  })
})
