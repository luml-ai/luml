import { describe, expect, it, vi } from 'vitest'
import { TarAttachmentsProvider } from '@luml/attachments'

describe('TarAttachmentsProvider with a supplied index', () => {
  it('reads attachment bytes from the tar range without fetching the index again', async () => {
    const bytes = new Uint8Array([1, 2, 3]).buffer
    const getFileFromBucket = vi.fn().mockResolvedValue(bytes)
    const provider = new TarAttachmentsProvider({
      downloader: { url: 'https://download.test/model', getFileFromBucket },
      fileIndex: {
        'attachments.tar': [100, 50],
        'attachments.index.json': [150, 20],
      },
      attachmentsIndex: { 'attachments/report.pdf': [10, 3] },
      findAttachmentsTarPath: () => 'attachments.tar',
      findAttachmentsIndexPath: () => 'attachments.index.json',
    })

    await provider.init()
    const content = await provider.getAttachmentContent('attachments/report.pdf')

    expect(provider.getTree()).toEqual([
      { name: 'report.pdf', path: 'attachments/report.pdf', type: 'file', size: 3 },
    ])
    expect(content.size).toBe(3)
    expect(content.blob.size).toBe(3)
    expect(getFileFromBucket).toHaveBeenCalledOnce()
    expect(getFileFromBucket).toHaveBeenCalledWith(
      { 'attachments/report.pdf': [10, 3] },
      'attachments/report.pdf',
      true,
      100,
    )
  })
})
