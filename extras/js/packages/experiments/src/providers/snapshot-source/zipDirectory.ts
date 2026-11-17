import { SnapshotTooLargeForBrowserError } from './errors'
import { browserTransport, readSourceRange, type SnapshotTransport } from './httpSource'
import type { SnapshotSourceRef } from './sourceLocation'

/**
 * JSZip reads entry sizes as signed 32-bit integers and returns one `Uint8Array`, and Chromium
 * does not allocate an ArrayBuffer of 2 GiB or more, so a larger `exp.db` never opens.
 */
export const MAX_ZIP_ENTRY_BYTES = 2 ** 31

export const ZIP_SNAPSHOT_ENTRY = 'exp.db'

// The end record is 22 bytes plus a comment of up to 64 KiB; the rest is for the directory.
const ZIP_TAIL_BYTES = 128 * 1024

const END_RECORD_SIGNATURE = 0x06054b50
const END_RECORD_SIZE = 22
const MAX_COMMENT_SIZE = 0xffff
const DIRECTORY_ENTRY_SIGNATURE = 0x02014b50
const DIRECTORY_ENTRY_SIZE = 46
const ZIP64_MARKER = 0xffffffff
const ZIP64_EXTRA_ID = 0x0001

function findEndRecord(view: DataView): number | null {
  const lowest = Math.max(0, view.byteLength - END_RECORD_SIZE - MAX_COMMENT_SIZE)
  for (let at = view.byteLength - END_RECORD_SIZE; at >= lowest; at--) {
    if (view.getUint32(at, true) !== END_RECORD_SIGNATURE) continue
    if (at + END_RECORD_SIZE + view.getUint16(at + 20, true) === view.byteLength) return at
  }
  return null
}

/** The 64-bit uncompressed size, the first field of the ZIP64 extra block; the marker without it. */
function zip64UncompressedSize(view: DataView, start: number, end: number): number {
  for (let at = start; at + 4 <= end; ) {
    const id = view.getUint16(at, true)
    const length = view.getUint16(at + 2, true)
    if (id === ZIP64_EXTRA_ID && length >= 8 && at + 12 <= end) {
      return Number(view.getBigUint64(at + 4, true))
    }
    at += 4 + length
  }
  return ZIP64_MARKER
}

/**
 * The uncompressed size of entry `name`, read from the central directory found in `tail`, the
 * last bytes of a zip of `zipSize` bytes. A ZIP64 size comes from the entry's extra block, or
 * is the marker 0xFFFFFFFF, which is above the limit, when it cannot be read. Null when
 * the directory is not in `tail`, cannot be parsed or has no such entry.
 */
export function zipEntrySize(tail: Uint8Array, zipSize: number, name: string): number | null {
  const view = new DataView(tail.buffer, tail.byteOffset, tail.byteLength)
  const end = findEndRecord(view)
  if (end === null) return null
  const entries = view.getUint16(end + 10, true)
  const directorySize = view.getUint32(end + 12, true)
  const directoryOffset = view.getUint32(end + 16, true)
  if (directorySize === ZIP64_MARKER || directoryOffset === ZIP64_MARKER) return ZIP64_MARKER
  const tailStart = zipSize - tail.length
  let at = directoryOffset - tailStart
  const directoryEnd = at + directorySize
  if (at < 0 || directoryEnd > end) return null
  const decoder = new TextDecoder()
  for (let index = 0; index < entries; index++) {
    if (at + DIRECTORY_ENTRY_SIZE > directoryEnd) return null
    if (view.getUint32(at, true) !== DIRECTORY_ENTRY_SIGNATURE) return null
    const compressedSize = view.getUint32(at + 20, true)
    const uncompressedSize = view.getUint32(at + 24, true)
    const nameLength = view.getUint16(at + 28, true)
    const extraLength = view.getUint16(at + 30, true)
    const commentLength = view.getUint16(at + 32, true)
    const nameStart = at + DIRECTORY_ENTRY_SIZE
    if (nameStart + nameLength > directoryEnd) return null
    if (decoder.decode(tail.subarray(nameStart, nameStart + nameLength)) === name) {
      if (uncompressedSize !== ZIP64_MARKER) {
        return compressedSize === ZIP64_MARKER ? ZIP64_MARKER : uncompressedSize
      }
      const extraStart = nameStart + nameLength
      return zip64UncompressedSize(view, extraStart, Math.min(extraStart + extraLength, end))
    }
    at = nameStart + nameLength + extraLength + commentLength
  }
  return null
}

export function assertZipEntryFits(modelId: string, size: number | null): void {
  if (size !== null && size >= MAX_ZIP_ENTRY_BYTES) {
    throw new SnapshotTooLargeForBrowserError(modelId, size, MAX_ZIP_ENTRY_BYTES)
  }
}

/**
 * Reads the tail of a zipped snapshot member by Range and fails with
 * `SnapshotTooLargeForBrowserError` when its `exp.db` is too large, before the member is
 * downloaded. When the tail cannot be read (the storage ignores Range, a request fails) or
 * parsed, it returns and the caller downloads the member as before; the provider checks the
 * directory of the downloaded zip again before inflating it.
 */
export async function assertZipSnapshotFits(
  modelId: string,
  source: SnapshotSourceRef,
  memberOffset: number,
  memberSize: number,
  signal?: AbortSignal,
  transport: SnapshotTransport = browserTransport,
): Promise<void> {
  // A member this small costs about as much to download whole, and the caller checks it then.
  if (memberSize <= ZIP_TAIL_BYTES) return
  let tail: Uint8Array | null
  try {
    const start = memberOffset + memberSize - ZIP_TAIL_BYTES
    tail = await readSourceRange(transport, modelId, source, start, ZIP_TAIL_BYTES, signal)
  } catch (error) {
    if ((error as { name?: unknown } | null)?.name === 'AbortError') throw error
    return
  }
  if (tail) assertZipEntryFits(modelId, zipEntrySize(tail, memberSize, ZIP_SNAPSHOT_ENTRY))
}
