import {
  CompressionType,
  compressionRegistry,
  Data,
  Int64,
  RecordBatch,
  RecordBatchReader,
  Table,
  Vector,
  tableFromIPC,
  Type,
} from 'apache-arrow'
import * as compat from '@uwdata/flechette'
import { decompress as lz4 } from 'lz4js'
import { decompress as zstd } from 'fzstd'
import { formatTimestamp } from './timestamp'
import { scaledDecimal } from './decimal'

interface FieldType {
  typeId: number
  unit?: number
  scale?: number
  children?: readonly { name: string; type: FieldType }[] | null
  dictionary?: FieldType
}

function arrowValue(value: any, type: FieldType): any {
  if (value == null) return value
  if (type.dictionary) return arrowValue(value, type.dictionary)
  if (type.typeId === Type.Decimal) return scaledDecimal(String(value), type.scale!)
  if (type.typeId === Type.Timestamp) return formatTimestamp(value, type.unit! * 3)
  if (type.typeId === Type.Date) return new Date(value).toISOString()
  if (type.typeId === Type.Struct) {
    return Object.fromEntries(
      (type.children ?? []).map((field) => [field.name, arrowValue(value[field.name], field.type)]),
    )
  }
  if (
    type.children?.length === 1 &&
    typeof value[Symbol.iterator] === 'function' &&
    type.typeId !== Type.Map
  ) {
    return Array.from(value, (item) => arrowValue(item, type.children![0]!.type))
  }
  return value
}

// fzstd can return an unaligned window onto its work buffer. Arrow creates
// typed views (including BigInt64Array) directly over these bytes.
function decodeZstd(bytes: Uint8Array) {
  const result = zstd(bytes)
  return result.byteOffset % 8 ? result.slice() : result
}

const codecs = [
  [CompressionType.LZ4_FRAME, lz4],
  [CompressionType.ZSTD, decodeZstd],
] as const

function registerCodecs() {
  for (const [type, decode] of codecs) {
    const existing = compressionRegistry.get(type)
    if (!existing?.decode) compressionRegistry.set(type, { ...existing, decode })
  }
}

function decode(bytes: Uint8Array) {
  registerCodecs()
  try {
    return tableFromIPC(bytes)
  } catch (error) {
    if (!(error instanceof Error && error.message.startsWith('Unrecognized type:'))) throw error
    // Arrow JS 21 lacks the large-list and view layouts written by PyArrow and Polars.
    for (const [type, decode] of codecs) {
      if (!compat.getCompressionCodec(type)) {
        // Flechette treats a same-size encode result as an uncompressed buffer.
        compat.setCompressionCodec(type, {
          decode: (bytes) => decode(bytes),
          encode: (bytes) => bytes,
        })
      }
    }
    return compat.tableFromIPC(bytes, {
      useBigInt: true,
      useDecimalInt: true,
      useBigIntTimestamp: true,
    })
  }
}

// Read timestamp buffers as Int64 so Arrow's millisecond getter never rounds the ticks.
function rawTimestamps(data: Data): Data {
  if (data.typeId === Type.Timestamp) return data.clone(new Int64())
  if (!data.children.length && !data.dictionary) return data
  const copy = data.clone(
    data.type,
    data.offset,
    data.length,
    data.nullCount,
    data.buffers,
    data.children.map(rawTimestamps),
  )
  if (data.dictionary) copy.dictionary = new Vector(data.dictionary.data.map(rawTimestamps))
  return copy
}

const FILE_MAGIC = [0x41, 0x52, 0x52, 0x4f, 0x57, 0x31] // "ARROW1"

/**
 * The first record batches of a file cut short: an IPC file is its magic and padding, then the
 * stream format its footer indexes, so a prefix is read as a stream up to the last whole batch.
 */
function decodePrefix(bytes: Uint8Array, limit: number) {
  registerCodecs()
  const stream = FILE_MAGIC.every((byte, index) => bytes[index] === byte)
    ? bytes.subarray(8)
    : bytes
  const batches: RecordBatch[] = []
  let rows = 0
  try {
    for (const batch of RecordBatchReader.from(stream).open()) {
      batches.push(batch)
      rows += batch.numRows
      if (rows >= limit) break
    }
  } catch (error) {
    // The batch the prefix cut through; the ones before it are whole.
    if (!batches.length) throw error
  }
  if (!batches.length) throw new Error('The first rows of this file are too large to preview.')
  return new Table(batches)
}

/** `truncated`: the blob is only the start of the file; the rows it holds are shown. */
export async function readArrow(blob: Blob, limit: number, truncated = false) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  const table = truncated ? decodePrefix(bytes, limit) : decode(bytes)
  const fields = table.schema.fields
  const headers = fields.map((field) => field.name)
  const columns = fields.map((field, index) => {
    const column = table.getChildAt(index)!
    const vector = column instanceof Vector ? new Vector(column.data.map(rawTimestamps)) : column
    return { field, vector }
  })
  const rows = Array.from({ length: Math.min(limit, table.numRows) }, (_, index) =>
    columns.map(({ field, vector }) => arrowValue(vector.get(index), field.type)),
  )
  return {
    headers,
    rows,
    columnsCount: headers.length,
    // Unknown when only the start was read: shown as "first N rows".
    rowsCount: truncated ? -1 : table.numRows,
    positional: true,
  }
}
