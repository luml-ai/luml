import { describe, expect, it, vi } from 'vitest'
import { TarAttachmentsProvider } from '@luml/attachments'

describe('TarAttachmentsProvider with a supplied index', () => {
  it('reads only the requested Parquet bytes within the nested archive member', async () => {
    const getFileFromBucket = vi.fn()
    const readRange = vi.fn().mockResolvedValue(new Uint8Array([7, 8]).buffer)
    const path = 'attachments/__proto__/constructor/sample.parquet'
    const provider = new TarAttachmentsProvider({
      downloader: { url: 'https://download.test/model', getFileFromBucket, readRange },
      fileIndex: { 'attachments.tar': [100, 80], 'attachments.index.json': [180, 20] },
      attachmentsIndex: { [path]: [10, 35], 'broken.parquet': [79, 5] },
      findAttachmentsTarPath: () => 'attachments.tar',
      findAttachmentsIndexPath: () => 'attachments.index.json',
    })
    await provider.init()
    const source = await provider.getPreviewSource(path)
    if (typeof source === 'string' || source instanceof Blob)
      throw new Error('Expected a byte source')
    expect(source.byteLength).toBe(35)
    expect(readRange).not.toHaveBeenCalled()
    expect(new Uint8Array(await source.slice(33))).toEqual(new Uint8Array([7, 8]))
    expect(readRange).toHaveBeenCalledWith(143, 145)
    expect((await source.slice(35)).byteLength).toBe(0)
    await expect(source.slice(34, 36)).rejects.toThrow('Invalid attachment slice')
    await expect(provider.getPreviewSource('broken.parquet')).rejects.toThrow(
      'Invalid attachment range',
    )
    expect(readRange).toHaveBeenCalledTimes(1)
    expect(getFileFromBucket).not.toHaveBeenCalled()
  })

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
