import { SnapshotFormatError } from './errors'

export const SQLITE_HEADER_SIZE = 100

const SQLITE_MAGIC = 'SQLite format 3\0'
const LEGACY_JOURNAL_FORMAT = 1

export interface SqliteHeaderInfo {
  pageSize: number
  pageCount: number
}

function readPageSize(view: DataView): number {
  const raw = view.getUint16(16)
  // The header stores 65536 as 1 because it does not fit into two bytes.
  return raw === 1 ? 65536 : raw
}

/** Validates the 100-byte SQLite header of a snapshot member before any query touches it. */
export function validateSqliteHeader(
  modelId: string,
  header: Uint8Array,
  memberSize: number,
): SqliteHeaderInfo {
  if (header.length < SQLITE_HEADER_SIZE) {
    throw new SnapshotFormatError(modelId, `header is ${header.length} bytes, expected 100`)
  }
  const magic = String.fromCharCode(...header.subarray(0, SQLITE_MAGIC.length))
  if (magic !== SQLITE_MAGIC) throw new SnapshotFormatError(modelId, 'not an SQLite database')

  const view = new DataView(header.buffer, header.byteOffset, SQLITE_HEADER_SIZE)
  const pageSize = readPageSize(view)
  if (pageSize < 512 || pageSize > 65536 || (pageSize & (pageSize - 1)) !== 0) {
    throw new SnapshotFormatError(modelId, `invalid page size ${pageSize}`)
  }
  if (header[18] !== LEGACY_JOURNAL_FORMAT || header[19] !== LEGACY_JOURNAL_FORMAT) {
    throw new SnapshotFormatError(modelId, 'database is in WAL mode')
  }

  const changeCounter = view.getUint32(24)
  const versionValidFor = view.getUint32(92)
  const headerPageCount = view.getUint32(28)
  // The in-header page count is only trustworthy when it was written with the change counter.
  const pageCount =
    headerPageCount > 0 && changeCounter === versionValidFor
      ? headerPageCount
      : Math.floor(memberSize / pageSize)
  if (pageCount * pageSize > memberSize) {
    throw new SnapshotFormatError(
      modelId,
      `member is truncated: ${memberSize} bytes, database needs ${pageCount * pageSize}`,
    )
  }
  return { pageSize, pageCount }
}
