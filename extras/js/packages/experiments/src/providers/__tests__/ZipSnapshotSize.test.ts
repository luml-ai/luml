import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import JSZip from 'jszip'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import { SNAPSHOT_TOO_LARGE_FOR_BROWSER } from '../snapshot-source/errors'
import {
  assertZipEntryFits,
  assertZipSnapshotFits,
  MAX_ZIP_ENTRY_BYTES,
  zipEntrySize,
} from '../snapshot-source/zipDirectory'
import { craftedZip } from './helpers/craftedZip'
import { indexTar, memoryTransport, readFixtureTar, writeTar } from './helpers/snapshotSources'

const ZIP_FIXTURES = [
  'a_premigration_legacy_indexes',
  'a_premigration_wal_lost',
  'b_premigration',
  'c_sdk_0_1_0',
  'd_sdk_0_5_0',
  'e_baseline_quirk',
  'f_model_sdk_0_5_0',
  'l_gen1_twin',
  'n_gen1_fallback',
]
const URL = 'https://bucket.example/run.tar'

function hugeZip(): Uint8Array {
  return craftedZip([{ name: 'exp.db', size: 0, zip64Size: 3_811_495_936 }], '', 300_000)
}

async function realZip(files: Record<string, Uint8Array>, comment?: string): Promise<Uint8Array> {
  const zip = new JSZip()
  for (const [name, data] of Object.entries(files)) zip.file(name, data)
  return zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE', comment })
}

function fixtureZip(name: string): Uint8Array {
  const tar = readFixtureTar(name)
  const [member, [offset, size]] = Object.entries(indexTar(tar)).find(([path]) =>
    path.endsWith('exp.db.zip'),
  )!
  expect(member).toMatch(/exp\.db\.zip$/)
  return tar.slice(offset, offset + size)
}

function artifactWith(zip: Uint8Array) {
  const tar = writeTar([
    { name: 'meta.json', data: new TextEncoder().encode('{}') },
    { name: 'exp.db.zip', data: zip },
  ])
  const [offset, size] = indexTar(tar)['exp.db.zip']!
  return { tar, offset, size }
}

describe('zipEntrySize', () => {
  it('reads the uncompressed size of exp.db from a normal zip', async () => {
    const zip = await realZip({ 'exp.db': new Uint8Array(5000).fill(7) })
    expect(zipEntrySize(zip, zip.length, 'exp.db')).toBe(5000)
  })

  it('finds the directory behind a trailing comment', async () => {
    const zip = await realZip({ 'exp.db': new Uint8Array(300) }, 'a comment with PK\x05\x06 inside')
    expect(zipEntrySize(zip, zip.length, 'exp.db')).toBe(300)
  })

  it('does not take an end record signature in the comment for the real record', () => {
    // The backwards search meets the fake record 22 bytes before the end first; its comment
    // length (5) does not reach the end of the zip.
    const fake = '\x50\x4b\x05\x06' + '\x00'.repeat(16) + '\x05\x00'
    const zip = craftedZip([{ name: 'exp.db', size: 300 }], `comment ${fake}`)
    expect(zip.subarray(zip.length - 22, zip.length - 18)).toEqual(
      new Uint8Array([0x50, 0x4b, 0x05, 0x06]),
    )
    expect(zipEntrySize(zip, zip.length, 'exp.db')).toBe(300)
  })

  it('finds exp.db when it is not the first entry', async () => {
    const zip = await realZip({ 'meta.json': new Uint8Array(10), 'exp.db': new Uint8Array(1234) })
    expect(zipEntrySize(zip, zip.length, 'exp.db')).toBe(1234)
  })

  it('reads the directory from a tail of the zip', async () => {
    const zip = await realZip({ 'exp.db': new Uint8Array(100_000).map((_, i) => i * 31) })
    const tail = zip.subarray(zip.length - 200)
    expect(zipEntrySize(tail, zip.length, 'exp.db')).toBe(100_000)
  })

  it('reads a ZIP64 size from the extra block and checks that size', () => {
    const large = craftedZip([{ name: 'exp.db', size: 0, zip64Size: 3_811_495_936 }])
    expect(zipEntrySize(large, large.length, 'exp.db')).toBe(3_811_495_936)
    expect(() => assertZipEntryFits('m', zipEntrySize(large, large.length, 'exp.db'))).toThrow(
      expect.objectContaining({ code: SNAPSHOT_TOO_LARGE_FOR_BROWSER }),
    )
    const small = craftedZip([{ name: 'exp.db', size: 0, zip64Size: 100 }])
    expect(zipEntrySize(small, small.length, 'exp.db')).toBe(100)
    expect(() => assertZipEntryFits('m', zipEntrySize(small, small.length, 'exp.db'))).not.toThrow()
  })

  it('returns the ZIP64 marker when the extra block is too short to hold the size', () => {
    const zip = craftedZip([{ name: 'exp.db', size: 0, zip64Size: 100 }])
    const view = new DataView(zip.buffer)
    const extra = zip.length - 22 - 20
    expect(view.getUint16(extra, true)).toBe(0x0001)
    view.setUint16(extra + 2, 4, true)
    const size = zipEntrySize(zip, zip.length, 'exp.db')
    expect(size).toBe(0xffffffff)
    expect(() => assertZipEntryFits('m', size)).toThrow(
      expect.objectContaining({ code: SNAPSHOT_TOO_LARGE_FOR_BROWSER }),
    )
  })

  it('returns the ZIP64 marker without an extra block, which is above the limit', () => {
    const zip = craftedZip([{ name: 'exp.db', size: 0xffffffff }])
    const size = zipEntrySize(zip, zip.length, 'exp.db')
    expect(size).toBe(0xffffffff)
    expect(() => assertZipEntryFits('m', size)).toThrow(/unzips to 4294967295 bytes/)
  })

  it('returns null for garbage, a truncated tail or a missing entry', async () => {
    const zip = await realZip({ 'exp.db': new Uint8Array(100_000).map((_, i) => i * 31) })
    const garbage = new Uint8Array(4096).map((_, i) => (i * 7919) % 251)
    expect(zipEntrySize(garbage, garbage.length, 'exp.db')).toBeNull()
    expect(zipEntrySize(zip.subarray(zip.length - 30), zip.length, 'exp.db')).toBeNull()
    expect(zipEntrySize(zip.subarray(0, zip.length - 10), zip.length - 10, 'exp.db')).toBeNull()
    expect(zipEntrySize(new Uint8Array(0), 0, 'exp.db')).toBeNull()
    expect(zipEntrySize(zip, zip.length, 'other.db')).toBeNull()
  })

  it('fails at the limit and passes one byte below it', () => {
    const atLimit = craftedZip([{ name: 'exp.db', size: MAX_ZIP_ENTRY_BYTES }])
    const below = craftedZip([{ name: 'exp.db', size: MAX_ZIP_ENTRY_BYTES - 1 }])
    expect(() => assertZipEntryFits('m', zipEntrySize(atLimit, atLimit.length, 'exp.db'))).toThrow(
      expect.objectContaining({ code: SNAPSHOT_TOO_LARGE_FOR_BROWSER }),
    )
    expect(() => assertZipEntryFits('m', zipEntrySize(below, below.length, 'exp.db'))).not.toThrow()
    expect(() => assertZipEntryFits('m', null)).not.toThrow()
  })

  it.each(ZIP_FIXTURES)('reads the same size as JSZip inflates for fixture %s', async (name) => {
    const zip = fixtureZip(name)
    const inflated = await (await JSZip.loadAsync(zip)).file('exp.db')!.async('uint8array')
    expect(zipEntrySize(zip, zip.length, 'exp.db')).toBe(inflated.length)
  })
})

describe('assertZipSnapshotFits', () => {
  it('fails from the directory without requesting the member body', async () => {
    const { tar, offset, size } = artifactWith(hugeZip())
    const store = memoryTransport({ [URL]: tar })

    const check = assertZipSnapshotFits('m', URL, offset, size, undefined, store.transport)

    await expect(check).rejects.toMatchObject({
      code: SNAPSHOT_TOO_LARGE_FOR_BROWSER,
      modelId: 'm',
      size: 3_811_495_936,
      limit: MAX_ZIP_ENTRY_BYTES,
    })
    expect(size).toBeGreaterThan(300_000)
    expect(store.requests).toEqual([
      { kind: 'fetch', url: URL, offset: offset + size - 128 * 1024, length: 128 * 1024 },
    ])
  })

  it('passes a large member that fits after reading only its last 128 KiB', async () => {
    const stored = new JSZip().file('exp.db', new Uint8Array(400_000))
    const zip = await stored.generateAsync({ type: 'uint8array', compression: 'STORE' })
    const { tar, offset, size } = artifactWith(zip)
    expect(size).toBeGreaterThan(128 * 1024)
    const store = memoryTransport({ [URL]: tar })

    await assertZipSnapshotFits('m', URL, offset, size, undefined, store.transport)

    expect(store.requests).toEqual([
      { kind: 'fetch', url: URL, offset: offset + size - 128 * 1024, length: 128 * 1024 },
    ])
  })

  it('returns for a full download when the storage ignores Range', async () => {
    const { tar, offset, size } = artifactWith(hugeZip())
    const store = memoryTransport({ [URL]: tar })
    store.controls.ignoreRange = true

    await expect(
      assertZipSnapshotFits('m', URL, offset, size, undefined, store.transport),
    ).resolves.toBeUndefined()
  })

  it('accepts a Range answered with status 200', async () => {
    const { tar, offset, size } = artifactWith(hugeZip())
    const store = memoryTransport({ [URL]: tar })
    store.controls.rangeWith200 = true

    await expect(
      assertZipSnapshotFits('m', URL, offset, size, undefined, store.transport),
    ).rejects.toMatchObject({ code: SNAPSHOT_TOO_LARGE_FOR_BROWSER })
  })

  it('returns when the tail request fails, and when the tail is not a zip', async () => {
    const { tar, offset, size } = artifactWith(hugeZip())
    const failing = memoryTransport({ [URL]: tar })
    failing.controls.failingUrls.add(URL)
    await expect(
      assertZipSnapshotFits('m', URL, offset, size, undefined, failing.transport),
    ).resolves.toBeUndefined()

    const garbage = artifactWith(new Uint8Array(200_000).fill(9))
    const store = memoryTransport({ [URL]: garbage.tar })
    await expect(
      assertZipSnapshotFits('m', URL, garbage.offset, garbage.size, undefined, store.transport),
    ).resolves.toBeUndefined()
  })

  it('passes an aborted request on', async () => {
    const { tar, offset, size } = artifactWith(hugeZip())
    const store = memoryTransport({ [URL]: tar })
    const controller = new AbortController()
    controller.abort()
    const transport = {
      ...store.transport,
      fetch: async () => {
        throw new DOMException('Aborted', 'AbortError')
      },
    }
    await expect(
      assertZipSnapshotFits('m', URL, offset, size, controller.signal, transport),
    ).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('zipped snapshot too large for the browser', () => {
  let warn: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  })

  afterEach(() => warn.mockRestore())

  it('fails a fully downloaded zip from its directory, before inflating it', async () => {
    const provider = new ExperimentSnapshotDatabaseProvider()
    const buffer = hugeZip().buffer as ArrayBuffer

    const failures = await provider.init({ modelsInfo: [{ modelId: 'old', buffer }] })

    // JSZip would fail on the missing data with another error; this one comes first.
    expect(failures).toEqual([
      {
        modelId: 'old',
        error: { code: SNAPSHOT_TOO_LARGE_FOR_BROWSER, message: expect.any(String) },
      },
    ])
    expect(warn).toHaveBeenCalledOnce()
    expect(String(warn.mock.calls[0]?.[0])).toContain('unzips to 3811495936 bytes')
  })

  it('opens a small fixture zip without a tail read, from its one download', async () => {
    const zip = fixtureZip('d_sdk_0_5_0')
    const { tar, offset, size } = artifactWith(zip)
    const store = memoryTransport({ [URL]: tar })
    await assertZipSnapshotFits('m', URL, offset, size, undefined, store.transport)
    const provider = new ExperimentSnapshotDatabaseProvider()

    const failures = await provider.init({
      modelsInfo: [{ modelId: 'm', buffer: tar.slice(offset, offset + size).buffer }],
    })

    expect(failures).toEqual([])
    expect(size).toBeLessThan(128 * 1024)
    expect(store.requests).toEqual([])
    expect((await provider.getExperimentStatuses())[0]).toMatchObject({
      transport: 'zip-full',
      error: null,
    })
    expect(warn).not.toHaveBeenCalled()
  })
})

describe('a snapshot that failed to open, compared with one that opened', () => {
  let warn: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  })

  afterEach(() => warn.mockRestore())

  async function comparison() {
    const provider = new ExperimentSnapshotDatabaseProvider()
    await provider.init({
      modelsInfo: [
        { modelId: 'old', buffer: hugeZip().buffer as ArrayBuffer },
        { modelId: 'new', buffer: fixtureZip('d_sdk_0_5_0').buffer as ArrayBuffer },
      ],
    })
    return provider
  }

  it('gives empty trace and eval reads for the failed one instead of throwing', async () => {
    const provider = await comparison()

    expect(await provider.getTraceSpans('old', 't1')).toEqual([])
    expect(await provider.getTraceId({ modelId: 'old', datasetId: 'd', evalId: 'e' })).toBeNull()
    expect(await provider.getEvalAnnotations('old', 'd', 'e')).toEqual([])
    expect(await provider.getSpanAnnotations('old', 't1', 's1')).toEqual([])
    expect(await provider.getTracesAnnotationSummary('old')).toEqual({
      feedback: [],
      expectations: [],
    })
    expect(await provider.getTracesColumns('old')).toEqual({
      attributes: [],
      annotations_feedback: [],
      annotations_expectations: [],
    })
    await expect(provider.getTracesColumns('unknown')).rejects.toThrow('Database not found')
  })

  it('shows the one that opened in full and reports the failed one once', async () => {
    const provider = await comparison()
    const traceParams = { limit: 10, sort_by: 'created_at', order: 'desc', search: '', filters: [] }

    const traces = await provider.getTraces(traceParams as Parameters<typeof provider.getTraces>[0])
    expect(traces.length).toBeGreaterThan(0)
    expect((await provider.getTracesColumns('new')).attributes.length).toBeGreaterThan(0)
    expect(await provider.getDynamicMetricsNames()).not.toEqual([])
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.map(({ modelId, error }) => [modelId, error?.code ?? null])).toEqual([
      ['old', SNAPSHOT_TOO_LARGE_FOR_BROWSER],
      ['new', null],
    ])
    expect(warn).toHaveBeenCalledOnce()
  })
})
