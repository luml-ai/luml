import axios from 'axios'
import type { FileIndex } from '../api/artifacts/interfaces'
import type { DownloadUrlSource } from './presigned-url-cache'

export {
  PresignedUrlCache,
  PRESIGNED_URL_MIN_RENEW_AGE_MS,
  PRESIGNED_URL_REUSE_MS,
  sameDownloadLocation,
  toDownloadLocation,
} from './presigned-url-cache'
export type { DownloadLocation, DownloadRef, DownloadUrlSource } from './presigned-url-cache'

/**
 * A ranged read returned another number of bytes than asked for: the storage ignored Range
 * (a 200 with the whole object) or cut the transfer short. Not retried, since a renewed URL
 * gets the same answer.
 */
export class RangeLengthMismatchError extends Error {
  constructor(
    readonly fileName: string,
    readonly expected: number,
    readonly received: number,
  ) {
    super(`Range read of '${fileName}' returned ${received} of ${expected} bytes`)
    this.name = 'RangeLengthMismatchError'
  }
}

/** As axios' JSON response type did: text that is not JSON is handed over as text. */
function parseJsonOrText(bytes: ArrayBuffer): unknown {
  const text = new TextDecoder().decode(bytes)
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export class ModelDownloader {
  constructor(readonly urls: DownloadUrlSource) {}

  async getFileFromBucket<T = ArrayBuffer | Record<string, unknown>>(
    fileIndex: FileIndex,
    fileName: string,
    buffer?: boolean,
    outerOffset = 0,
    signal?: AbortSignal,
  ): Promise<T> {
    const range = this.getRangeHeader(fileIndex, fileName, outerOffset)
    const expected = fileIndex[fileName]?.[1] ?? 0
    // Status does not tell a range from a whole object (some storages answer 200 to both), so
    // the body is read as bytes and its length checked before it is parsed. A body longer than
    // the range is stopped at once: storage that ignores Range would send the whole object.
    // Its length comes back instead of bytes, so the mismatch is not retried with a renewed URL.
    const answer = await this.urls.withLocation(async ({ url, headers, credentials }) => {
      const tooLong = new AbortController()
      let received = 0
      try {
        const file = await axios.get<ArrayBuffer>(url, {
          headers: { ...headers, Range: range },
          responseType: 'arraybuffer',
          withCredentials: credentials === 'include',
          signal: signal ? AbortSignal.any([signal, tooLong.signal]) : tooLong.signal,
          onDownloadProgress: ({ loaded, total }) => {
            received = Math.max(loaded, total ?? 0)
            if (received > expected) tooLong.abort()
          },
        })
        return file.data
      } catch (error) {
        if (tooLong.signal.aborted && !signal?.aborted) return received
        throw error
      }
    })
    const receivedLength = typeof answer === 'number' ? answer : answer.byteLength
    if (typeof answer === 'number' || receivedLength !== expected) {
      throw new RangeLengthMismatchError(fileName, expected, receivedLength)
    }
    return (buffer ? answer : parseJsonOrText(answer)) as T
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
