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
    // Status does not tell a range from a whole object (some storages answer 200 to both), so
    // the body is read as bytes and its length checked before it is parsed.
    const bytes = await this.urls.withLocation(async ({ url, headers, credentials }) => {
      const file = await axios.get<ArrayBuffer>(url, {
        headers: { ...headers, Range: range },
        responseType: 'arraybuffer',
        withCredentials: credentials === 'include',
        signal,
      })
      return file.data
    })
    const expected = fileIndex[fileName]?.[1] ?? 0
    if (bytes.byteLength !== expected) {
      throw new RangeLengthMismatchError(fileName, expected, bytes.byteLength)
    }
    return (buffer ? bytes : parseJsonOrText(bytes)) as T
  }

  getRangeHeader(fileIndex: FileIndex, fileName: string, outerOffset = 0) {
    const range = fileIndex[fileName]
    if (!range) throw new Error('Model not include this file')
    const start = range[0] + outerOffset
    const end = start + range[1] - 1
    return `bytes=${start}-${end}`
  }
}
