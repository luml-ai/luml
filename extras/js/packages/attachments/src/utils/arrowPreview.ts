import { CompressionType, compressionRegistry, tableFromIPC, Type } from 'apache-arrow'
import * as compat from '@uwdata/flechette'
import { decompress as lz4 } from 'lz4js'
import { decompress as zstd } from 'fzstd'
import { scaledDecimal } from './decimal'

interface FieldType {
  typeId: number
  scale?: number
  children?: readonly { name: string; type: FieldType }[] | null
  dictionary?: FieldType
}

function arrowValue(value: any, type: FieldType): any {
  if (value == null) return value
  if (type.dictionary) return arrowValue(value, type.dictionary)
  if (type.typeId === Type.Decimal) return scaledDecimal(String(value), type.scale!)
  if (type.typeId === Type.Timestamp || type.typeId === Type.Date)
    return new Date(value).toISOString()
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

function decode(bytes: Uint8Array) {
  const codecs = [
    [CompressionType.LZ4_FRAME, lz4],
    [CompressionType.ZSTD, decodeZstd],
  ] as const
  for (const [type, decode] of codecs) {
    const existing = compressionRegistry.get(type)
    if (!existing?.decode) compressionRegistry.set(type, { ...existing, decode })
  }
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
    return compat.tableFromIPC(bytes, { useBigInt: true, useDecimalInt: true })
  }
}

export async function readArrow(blob: Blob, limit: number) {
  const table = decode(new Uint8Array(await blob.arrayBuffer()))
  const fields = table.schema.fields
  const headers = fields.map((field) => field.name)
  const columns = fields.map((field, index) => ({ field, vector: table.getChildAt(index)! }))
  const rows = Array.from({ length: Math.min(limit, table.numRows) }, (_, index) =>
    columns.map(({ field, vector }) => arrowValue(vector.get(index), field.type)),
  )
  return { headers, rows, columnsCount: headers.length, rowsCount: table.numRows, positional: true }
}
