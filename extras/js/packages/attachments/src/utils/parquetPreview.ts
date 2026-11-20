import {
  parquetMetadataAsync,
  parquetSchema,
  type AsyncBuffer,
  type ColumnChunk,
  type DecodedArray,
  type SchemaTree,
} from 'hyparquet'
import { assembleNested } from 'hyparquet/src/assemble.js'
import { parquetHeader, readPage } from 'hyparquet/src/column.js'
import { convert, DEFAULT_PARSERS } from 'hyparquet/src/convert.js'
import { getTreePath, getMaxRepetitionLevel } from 'hyparquet/src/schema.js'
import { compressors } from 'hyparquet-compressors'
import { formatTimestamp } from './timestamp'
import { scaledDecimal } from './decimal'

const parsers = {
  ...DEFAULT_PARSERS,
  timestampFromMilliseconds: (ticks: bigint) => formatTimestamp(ticks, 3),
  timestampFromMicroseconds: (ticks: bigint) => formatTimestamp(ticks, 6),
  timestampFromNanoseconds: (ticks: bigint) => formatTimestamp(ticks, 9),
}

// Page headers have variable-length Thrift metadata. Reuse the probe bytes
// in the page body, including when the whole page fits in the first read.
async function pageAt(file: AsyncBuffer, offset: number, end: number) {
  for (let length = 128; ; length *= 2) {
    const stop = Math.min(offset + length, end)
    const prefix = await file.slice(offset, stop)
    const reader = { view: new DataView(prefix), offset: 0 }
    let header
    try {
      header = parquetHeader(reader)
    } catch (error) {
      if (stop === end) throw error
      continue
    }
    const size = reader.offset + header.compressed_page_size
    if (!Number.isSafeInteger(size) || size < reader.offset || offset + size > end) {
      throw new Error('Invalid Parquet page size')
    }
    if (size > prefix.byteLength) {
      const bytes = new Uint8Array(size)
      bytes.set(new Uint8Array(prefix))
      bytes.set(new Uint8Array(await file.slice(stop, offset + size)), prefix.byteLength)
      reader.view = new DataView(bytes.buffer)
    }
    return { header, reader, size }
  }
}

function formatDecimal(value: unknown, scale: number): unknown {
  if (value == null) return value
  if (Array.isArray(value)) return value.map((item) => formatDecimal(item, scale))
  if (value instanceof Uint8Array) {
    let n = value[0]! & 128 ? -1n : 0n
    for (const byte of value) n = (n << 8n) | BigInt(byte)
    return scaledDecimal(String(n), scale)
  }
  return scaledDecimal(String(value), scale)
}

async function columnPrefix(
  file: AsyncBuffer,
  chunk: ColumnChunk,
  schema: SchemaTree,
  limit: number,
) {
  const meta = chunk.meta_data
  if (!meta || chunk.file_path) throw new Error('Expected a local Parquet column')
  const schemaPath = getTreePath(schema, meta.path_in_schema)
  const field = schemaPath[schemaPath.length - 1]!.element
  const scale =
    field.logical_type?.type === 'DECIMAL'
      ? field.logical_type.scale
      : field.converted_type === 'DECIMAL'
        ? (field.scale ?? 0)
        : undefined
  const decoder = {
    ...meta,
    pathInSchema: meta.path_in_schema,
    schemaPath,
    compressors,
    parsers,
    // Decode the physical integer or two's-complement bytes before applying scale.
    element:
      scale === undefined
        ? field
        : { ...field, converted_type: undefined, logical_type: undefined },
    utf8: scale === undefined,
  }
  let offset = Number(meta.dictionary_page_offset ?? meta.data_page_offset)
  const end = offset + Number(meta.total_compressed_size)
  if (offset < 0 || !Number.isSafeInteger(end) || end > file.byteLength)
    throw new Error('Invalid Parquet column range')
  const repeated = getMaxRepetitionLevel(schemaPath) > 0
  let dictionary: DecodedArray | undefined
  const values: any[] = []
  while (offset < end) {
    const { header, reader, size } = await pageAt(file, offset, end)
    offset += size
    const { data } = readPage(reader, header, decoder, dictionary, values, 0)
    if (!data) continue
    if (header.type === 'DICTIONARY_PAGE') {
      dictionary = convert(data, decoder)
      continue
    }
    if (data !== values) {
      for (const value of data) {
        values.push(value)
        if (values.length === limit) break
      }
    }
    // A repeated V1 row may continue on the next page. V2 pages end on row boundaries.
    if (
      values.length > limit ||
      (values.length === limit && (!repeated || header.type === 'DATA_PAGE_V2'))
    )
      break
  }
  if (values.length < limit) throw new Error('Incomplete Parquet column')
  const prefix = values.slice(0, limit)
  return [
    meta.path_in_schema.join('.'),
    scale === undefined ? prefix : prefix.map((value) => formatDecimal(value, scale)),
  ] as const
}

export async function readParquet(file: AsyncBuffer, limit: number) {
  const metadata = await parquetMetadataAsync(file, { initialFetchSize: 8 })
  const schema = parquetSchema(metadata)
  const headers = schema.children.map((field) => field.element.name)
  const rows = []
  for (const group of metadata.row_groups) {
    const count = Math.min(limit - rows.length, Number(group.num_rows))
    if (!count) continue
    const columns = new Map(
      await Promise.all(group.columns.map((chunk) => columnPrefix(file, chunk, schema, count))),
    )
    for (const field of schema.children) {
      if (field.children.length) assembleNested(columns, field, parsers)
    }
    for (let i = 0; i < count; i++)
      rows.push(Object.fromEntries(headers.map((name) => [name, columns.get(name)![i]])))
    if (rows.length === limit) break
  }
  return { headers, rows, columnsCount: headers.length, rowsCount: Number(metadata.num_rows) }
}
