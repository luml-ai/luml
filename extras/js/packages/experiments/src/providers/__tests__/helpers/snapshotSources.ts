import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { SnapshotTransport } from '../../snapshot-source/httpSource'

export const FIXTURES_DIR = resolve(
  __dirname,
  '../../../../../../../../sdk/python/sdk/tests/fixtures/experiment_snapshots',
)

export function readFixtureTar(name: string): Uint8Array {
  return new Uint8Array(readFileSync(resolve(FIXTURES_DIR, `${name}.tar`)))
}

function readTarString(block: Uint8Array, start: number, length: number): string {
  const bytes = block.subarray(start, start + length)
  const end = bytes.indexOf(0)
  return new TextDecoder().decode(end === -1 ? bytes : bytes.subarray(0, end))
}

function parsePaxPath(record: Uint8Array): string | null {
  const match = /(?:^|\n)\d+ path=([^\n]*)\n/.exec(new TextDecoder().decode(record))
  return match?.[1] ?? null
}

/** Builds the `file_index` the platform stores for an artifact: member name -> [data offset, size]. */
export function indexTar(archive: Uint8Array): Record<string, [number, number]> {
  const index: Record<string, [number, number]> = {}
  let offset = 0
  let longName: string | null = null
  while (offset + 512 <= archive.length) {
    const header = archive.subarray(offset, offset + 512)
    if (header.every((byte) => byte === 0)) break
    const size = parseInt(readTarString(header, 124, 12).trim() || '0', 8)
    const type = String.fromCharCode(header[156] ?? 0)
    const dataOffset = offset + 512
    const data = archive.subarray(dataOffset, dataOffset + size)
    if (type === 'x') {
      longName = parsePaxPath(data)
    } else if (type === 'L') {
      longName = readTarString(data, 0, size)
    } else {
      const prefix = readTarString(header, 345, 155)
      const shortName = readTarString(header, 0, 100)
      const name = longName ?? (prefix ? `${prefix}/${shortName}` : shortName)
      if (type === '0' || type === '\0') index[name] = [dataOffset, size]
      longName = null
    }
    offset = dataOffset + Math.ceil(size / 512) * 512
  }
  return index
}

function writeOctal(header: Uint8Array, start: number, length: number, value: number): void {
  const text = value.toString(8).padStart(length - 1, '0')
  header.set(new TextEncoder().encode(text), start)
}

/** Minimal ustar writer for test artifacts; long names use the 155-byte prefix field. */
export function writeTar(entries: { name: string; data: Uint8Array }[]): Uint8Array {
  const blocks: Uint8Array[] = []
  for (const { name, data } of entries) {
    const header = new Uint8Array(512)
    const split = name.length > 100 ? name.lastIndexOf('/') : -1
    const encoder = new TextEncoder()
    header.set(encoder.encode(split === -1 ? name : name.slice(split + 1)), 0)
    if (split !== -1) header.set(encoder.encode(name.slice(0, split)), 345)
    writeOctal(header, 100, 8, 0o644)
    writeOctal(header, 108, 8, 0)
    writeOctal(header, 116, 8, 0)
    writeOctal(header, 124, 12, data.length)
    writeOctal(header, 136, 12, 0)
    header[156] = '0'.charCodeAt(0)
    header.set(encoder.encode('ustar\x0000'), 257)
    header.fill(' '.charCodeAt(0), 148, 156)
    const checksum = header.reduce((sum, byte) => sum + byte, 0)
    header.set(encoder.encode(checksum.toString(8).padStart(6, '0') + '\0 '), 148)
    blocks.push(header)
    const padded = new Uint8Array(Math.ceil(data.length / 512) * 512)
    padded.set(data)
    blocks.push(padded)
  }
  blocks.push(new Uint8Array(1024))
  const archive = new Uint8Array(blocks.reduce((sum, block) => sum + block.length, 0))
  let offset = 0
  for (const block of blocks) {
    archive.set(block, offset)
    offset += block.length
  }
  return archive
}

export interface RecordedRequest {
  kind: 'fetch' | 'range'
  url: string
  offset: number
  length: number
}

export interface MemoryTransportControls {
  /** Answer every request with status 200 and the whole object. */
  ignoreRange: boolean
  /** Honour Range but answer status 200 without `Content-Range`, as some S3 clones do. */
  rangeWith200: boolean
  failingUrls: Set<string>
}

function parseRange(header: string | null): [number, number] | null {
  const match = header ? /^bytes=(\d+)-(\d+)$/.exec(header) : null
  return match ? [Number(match[1]), Number(match[2])] : null
}

/** An in-memory object store that speaks the transport API, with request logging and faults. */
export function memoryTransport(files: Record<string, Uint8Array>) {
  const requests: RecordedRequest[] = []
  const controls: MemoryTransportControls = {
    ignoreRange: false,
    rangeWith200: false,
    failingUrls: new Set(),
  }
  const transport: SnapshotTransport = {
    fetch: async (input, init) => {
      const url = String(input)
      const bytes = files[url]
      if (!bytes || controls.failingUrls.has(url)) return new Response('denied', { status: 403 })
      const range = parseRange(new Headers(init?.headers).get('Range'))
      if (!range || controls.ignoreRange) {
        requests.push({ kind: 'fetch', url, offset: 0, length: bytes.length })
        return new Response(bytes.slice(), { status: 200 })
      }
      const [start, end] = range
      requests.push({ kind: 'fetch', url, offset: start, length: end - start + 1 })
      const body = bytes.slice(start, end + 1)
      if (controls.rangeWith200) return new Response(body, { status: 200 })
      return new Response(body, {
        status: 206,
        headers: { 'Content-Range': `bytes ${start}-${end}/${bytes.length}` },
      })
    },
    readRangeSync: ({ url }, offset, length) => {
      const bytes = files[url]
      if (!bytes || controls.failingUrls.has(url))
        throw new Error('Range request returned status 403')
      if (controls.ignoreRange) {
        requests.push({ kind: 'range', url, offset: 0, length: bytes.length })
        return bytes.slice()
      }
      requests.push({ kind: 'range', url, offset, length })
      return bytes.slice(offset, offset + length)
    },
  }
  return { transport, requests, controls }
}
