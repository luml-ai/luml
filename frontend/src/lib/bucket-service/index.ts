import axios from 'axios'
import type { FileIndex } from '../api/artifacts/interfaces'

export class ModelDownloader {
  url: string
  private hasFetched = false

  constructor(
    url: string,
    private refreshUrl?: () => Promise<string>,
  ) {
    this.url = url
  }

  async getFileFromBucket<T = ArrayBuffer | Record<string, unknown>>(
    fileIndex: FileIndex,
    fileName: string,
    buffer?: boolean,
    outerOffset = 0,
    signal?: AbortSignal,
  ): Promise<T> {
    const range = this.getRangeHeader(fileIndex, fileName, outerOffset)
    const url = this.hasFetched && this.refreshUrl ? await this.refreshUrl() : this.url
    this.hasFetched = true
    const file = await axios.get(url, {
      headers: { Range: range },
      responseType: buffer ? 'arraybuffer' : 'json',
      signal,
    })
    return file.data
  }

  getRangeHeader(fileIndex: FileIndex, fileName: string, outerOffset = 0) {
    const range = fileIndex[fileName]
    if (!range) throw new Error('Model not include this file')
    const start = range[0] + outerOffset
    const end = start + range[1] - 1
    return `bytes=${start}-${end}`
  }

  async readRange(start: number, end: number): Promise<ArrayBuffer> {
    const headers = { Range: `bytes=${start}-${end - 1}` }
    let response = await fetch(this.url, { headers })
    if ((response.status === 401 || response.status === 403) && this.refreshUrl) {
      await response.body?.cancel()
      this.url = await this.refreshUrl()
      response = await fetch(this.url, { headers })
    }
    // Cross-origin buckets don't always expose Content-Range to scripts.
    const contentRange = response.headers.get('Content-Range')
    if (
      response.status !== 206 ||
      (contentRange !== null && !contentRange.startsWith(`bytes ${start}-${end - 1}/`))
    ) {
      await response.body?.cancel()
      throw new Error('The storage server did not return the requested byte range')
    }
    const bytes = await response.arrayBuffer()
    if (bytes.byteLength !== end - start) throw new Error('Incomplete storage byte range')
    return bytes
  }
}
