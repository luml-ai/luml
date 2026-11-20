import { beforeAll, describe, expect, it } from 'vitest'
import JSZip from 'jszip'
import sqlite3InitModule from '@sqlite.org/sqlite-wasm'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import {
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
} from '../snapshot-source/errors'
import type { ModelSnapshot } from '@/interfaces/interfaces'
import { indexTar, memoryTransport, readFixtureTar, writeTar } from './helpers/snapshotSources'

const MODEL = 'large'
const URL_A = 'https://bucket.test/large?sig=a'
const URL_B = 'https://bucket.test/large?sig=b'
const CHUNK = 64 * 1024
const BULK_KEYS = 40
const BULK_STEPS = 5000
const BULK_DATASET = 'bulk_set'
const MEMBER_NAME =
  'meta_artifacts/dataforce.studio~c~~c~experiment_snapshot~c~v2~~et~~00000000000000000000000000000000/exp.db'

/**
 * A revision 2 experiment several MiB large: the raw fixture plus metrics logged step by step
 * (as the SDK does), evals and traces, vacuumed with 16 KiB pages.
 */
async function buildLargeSnapshot(base: Uint8Array): Promise<Uint8Array> {
  const sqlite3 = await sqlite3InitModule()
  const { capi, wasm } = sqlite3
  const db = new sqlite3.oo1.DB(':memory:')
  const pointer = wasm.allocFromTypedArray(base)
  const flags = capi.SQLITE_DESERIALIZE_FREEONCLOSE | capi.SQLITE_DESERIALIZE_RESIZEABLE
  expect(capi.sqlite3_deserialize(db, 'main', pointer, base.length, base.length, flags)).toBe(0)
  db.transaction(() => {
    const metric = db.prepare('INSERT INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)')
    for (let step = 0; step < BULK_STEPS; step++) {
      for (let key = 0; key < BULK_KEYS; key++) {
        metric.bind([`bulk_metric_${key}`, Math.sin(step * 0.01 + key), step]).stepReset()
      }
    }
    metric.finalize()
    const evalRow = db.prepare(
      'INSERT INTO evals (id, dataset_id, inputs, outputs, scores) VALUES (?, ?, ?, ?, ?)',
    )
    for (let index = 0; index < 2000; index++) {
      const id = `bulk_${String(index).padStart(5, '0')}`
      evalRow
        .bind([
          id,
          BULK_DATASET,
          JSON.stringify({ question: `question ${index} `.repeat(8) }),
          JSON.stringify({ answer: `answer ${index}` }),
          JSON.stringify({ accuracy: (index % 10) / 10 }),
        ])
        .stepReset()
    }
    evalRow.finalize()
    const span = db.prepare(
      `INSERT INTO spans (trace_id, span_id, parent_span_id, name, start_time_unix_nano,
       end_time_unix_nano, attributes) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    )
    for (let trace = 0; trace < 300; trace++) {
      for (let index = 0; index < 4; index++) {
        const start = 1_700_000_000_000_000_000n + BigInt(trace * 1000 + index)
        span
          .bind([
            `bulk_trace_${trace}`,
            `span_${index}`,
            index ? 'span_0' : null,
            `step ${index}`,
            start,
            start + 500n,
            JSON.stringify({ 'gen_ai.request.model': 'bulk' }),
          ])
          .stepReset()
      }
    }
    span.finalize()
  })
  db.exec('VACUUM')
  const bytes = capi.sqlite3_js_db_export(db)
  db.close()
  return bytes
}

interface LargeArtifact {
  db: Uint8Array
  tar: Uint8Array
  offset: number
  size: number
}

async function largeArtifact(): Promise<LargeArtifact> {
  const fixture = readFixtureTar('g_raw_sdk_0_5_0')
  const [baseOffset, baseSize] = indexTar(fixture)['exp.db']!
  const db = await buildLargeSnapshot(fixture.slice(baseOffset, baseOffset + baseSize))
  const tar = writeTar([
    { name: 'manifest.json', data: new TextEncoder().encode('{}') },
    { name: MEMBER_NAME, data: db },
  ])
  const [offset, size] = indexTar(tar)[MEMBER_NAME]!
  return { db, tar, offset, size }
}

async function zipProvider(db: Uint8Array) {
  const zip = new JSZip()
  zip.file('exp.db', db)
  const provider = new ExperimentSnapshotDatabaseProvider()
  const buffer = await zip.generateAsync({ type: 'arraybuffer' })
  await provider.init({ modelsInfo: [{ modelId: MODEL, buffer }] })
  return provider
}

async function rangeProvider(artifact: LargeArtifact) {
  const store = memoryTransport({ [URL_A]: artifact.tar, [URL_B]: artifact.tar })
  const provider = new ExperimentSnapshotDatabaseProvider({ transport: store.transport })
  const source = {
    kind: 'range',
    url: URL_A,
    offset: artifact.offset,
    size: artifact.size,
  } as const
  await provider.init({ modelsInfo: [{ modelId: MODEL, source }] })
  return { provider, ...store }
}

function databaseOf(provider: ExperimentSnapshotDatabaseProvider) {
  return (provider as unknown as { _modelsSnapshots: ModelSnapshot[] })._modelsSnapshots[0]!
    .database
}

const evalParams = {
  limit: 20,
  sort_by: 'created_at' as const,
  order: 'asc' as const,
  dataset_id: BULK_DATASET,
  search: '',
  filters: [],
}
const traceParams = {
  limit: 20,
  sort_by: 'created_at' as const,
  order: 'desc' as const,
  search: '',
  filters: [],
}

type ReadCall = [string, (provider: ExperimentSnapshotDatabaseProvider) => Promise<unknown>]

const READ_CALLS: ReadCall[] = [
  ['getDynamicMetricsNames', (p) => p.getDynamicMetricsNames()],
  ['getDynamicMetricData', (p) => p.getDynamicMetricData('bulk_metric_7')],
  ['getDynamicMetricData fixture', (p) => p.getDynamicMetricData('train_loss')],
  ['getStaticParamsList', (p) => p.getStaticParamsList()],
  ['getUniqueDatasetsIds', (p) => p.getUniqueDatasetsIds()],
  ['getNextEvalsByDatasetId', (p) => p.getNextEvalsByDatasetId(evalParams)],
  ['getFreshEvalsByDatasetId', (p) => p.getFreshEvalsByDatasetId(evalParams)],
  ['getAllDatasetEvals', (p) => p.getAllDatasetEvals({ ...evalParams, dataset_id: 'qa_set' })],
  ['getBatchExperimentEvals', (p) => p.getBatchExperimentEvals({ dataset_id: BULK_DATASET })],
  ['getEvalsColumns', (p) => p.getEvalsColumns('qa_set')],
  ['getDatasetAverageScores', (p) => p.getDatasetAverageScores(BULK_DATASET, 'question 1')],
  ['getEvalAnnotations', (p) => p.getEvalAnnotations(MODEL, 'qa_set', 'e1')],
  ['getEvalsDatasetAnnotationsSummary', (p) => p.getEvalsDatasetAnnotationsSummary('qa_set')],
  ['getEvalById', (p) => p.getEvalById(MODEL, 'bulk_01234')],
  ['getTraces', (p) => p.getTraces(traceParams)],
  ['getFreshTraces', (p) => p.getFreshTraces(traceParams)],
  ['getAllTraces', (p) => p.getAllTraces({ ...traceParams, search: 'bulk_trace_1' })],
  ['getTraceSpans', (p) => p.getTraceSpans(MODEL, 'bulk_trace_17')],
  ['getTraceId', (p) => p.getTraceId({ modelId: MODEL, datasetId: 'qa_set', evalId: 'e1' })],
  ['getSpanAnnotations', (p) => p.getSpanAnnotations(MODEL, 'bulk_trace_17', 'span_0')],
  ['getTracesAnnotationSummary', (p) => p.getTracesAnnotationSummary(MODEL)],
  ['getTracesColumns', (p) => p.getTracesColumns(MODEL)],
]

describe('range-backed snapshot provider on a large revision 2 experiment', () => {
  let artifact: LargeArtifact

  beforeAll(async () => {
    artifact = await largeArtifact()
  }, 60_000)

  it('builds a member large enough that range reads are measurably cheaper', () => {
    expect(artifact.size).toBeGreaterThan(8 * 1024 * 1024)
    expect(artifact.offset).toBeGreaterThan(0)
  })

  it('returns the same results as the in-memory zip path for every read method', async () => {
    const inMemory = await zipProvider(artifact.db)
    const { provider: ranged } = await rangeProvider(artifact)

    for (const [name, read] of READ_CALLS) {
      expect({ name, result: await read(ranged) }).toEqual({ name, result: await read(inMemory) })
    }
  })

  async function costOf(read: (provider: ExperimentSnapshotDatabaseProvider) => unknown) {
    const { provider, requests } = await rangeProvider(artifact)
    const opened = requests.length
    await read(provider)
    const issued = requests.slice(opened)
    return {
      opened,
      requests: issued.length,
      bytes: issued.reduce((sum, request) => sum + request.length, 0),
      largest: Math.max(0, ...issued.map((request) => request.length)),
    }
  }

  it('opens with one probe that seeds the first chunk, and answers a point query with a few chunks', async () => {
    const point = await costOf((provider) =>
      databaseOf(provider).exec(
        "SELECT * FROM evals WHERE dataset_id = 'bulk_set' AND id = 'bulk_01234'",
      ),
    )
    expect(point.opened).toBe(1)
    expect(point.requests).toBeLessThanOrEqual(3)
    // One request may carry a filled one-chunk hole along.
    expect(point.bytes).toBeLessThanOrEqual(4 * CHUNK)

    const evalWithAnnotations = await costOf((provider) =>
      provider.getEvalById(MODEL, 'bulk_01234'),
    )
    expect(evalWithAnnotations.requests).toBeLessThanOrEqual(6)
    expect(evalWithAnnotations.bytes).toBeLessThan(artifact.size / 16)
  })

  it('reads a metric series of a revision 2 DB with a few growing sequential requests', async () => {
    const series = await costOf((provider) => provider.getDynamicMetricData('bulk_metric_9'))

    expect(series.requests).toBeLessThanOrEqual(14)
    expect(series.largest).toBe(4 * 1024 * 1024 + CHUNK)
    expect(series.bytes).toBeLessThanOrEqual(artifact.size)
  })

  it('turns a full table scan into a few large sequential reads', async () => {
    const scan = await costOf((provider) => {
      const rows = databaseOf(provider).exec('SELECT COUNT(*), SUM(value) FROM dynamic_metrics')
      expect(rows[0]!.values[0]![0]).toBe(BULK_KEYS * BULK_STEPS + 111)
    })

    expect(scan.requests).toBeLessThanOrEqual(12)
    expect(scan.largest).toBe(4 * 1024 * 1024 + CHUNK)
    expect(scan.bytes).toBeLessThanOrEqual(artifact.size)
  })

  it('fails a read on an expired URL with a typed error and recovers after a URL change', async () => {
    const { provider, controls } = await rangeProvider(artifact)
    controls.failingUrls.add(URL_A)

    const failed = provider.getNextEvalsByDatasetId(evalParams)
    await expect(failed).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
    await expect(failed).rejects.toMatchObject({ modelId: MODEL })

    await provider.setSourceUrl(MODEL, URL_B)
    const page = await provider.getNextEvalsByDatasetId(evalParams)
    expect(page.map((item) => item.id)[0]).toBe('bulk_00000')
    expect(await provider.getTransportStats()).toEqual([
      expect.objectContaining({ modelId: MODEL, transport: 'raw-range' }),
    ])
  })

  it('downloads the whole object at most once when the storage stops honouring Range', async () => {
    const { provider, requests, controls } = await rangeProvider(artifact)
    controls.ignoreRange = true
    const opened = requests.length

    const reads = [
      provider.getDynamicMetricData('bulk_metric_3'),
      provider.getAllTraces(traceParams),
      provider.getDynamicMetricData('bulk_metric_30'),
    ]
    for (const read of reads) {
      await expect(read).rejects.toBeInstanceOf(SnapshotRangeUnsupportedError)
    }

    const issued = requests.slice(opened)
    expect(issued).toEqual([{ kind: 'range', url: URL_A, offset: 0, length: artifact.tar.length }])
  })

  it('ignores a URL change for a snapshot that is not range-backed', async () => {
    const provider = await zipProvider(artifact.db)

    await expect(provider.setSourceUrl(MODEL, URL_B)).resolves.toBe(false)
  })
})
