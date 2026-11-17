import { beforeAll, describe, expect, it } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import { TOO_MANY_BUCKETS, type ExperimentResult } from '@/metric-buckets/types'
import { oracleBuckets, revision3Database, type MetricPoint } from './helpers/metricDatabases'
import { memoryTransport } from './helpers/snapshotSources'
import { SnapshotSourceExpiredError } from '../snapshot-source/errors'

const KEYS = ['train/loss', 'train/grad_norm', 'eval/accuracy', 'lr']
const CHUNK = 64 * 1024
// 1000 buckets of level 3 (64 steps each) in the middle of the run.
const WINDOW = { start_step: 64 * 500, end_step: 64 * 1500 - 1, level: 3 }

function bulkPoints(stepsPerKey: number): MetricPoint[] {
  return KEYS.flatMap((key, index) =>
    Array.from({ length: stepsPerKey }, (_, step) => ({
      key,
      step,
      value: Math.sin(step * 0.001 + index) * (index + 1),
    })),
  )
}

interface Measured {
  dbSize: number
  open: { requests: number; bytes: number }
  catalog: { requests: number; bytes: number }
  buckets: { requests: number; bytes: number }
  rejected: { requests: number; bytes: number }
  names: { requests: number; bytes: number }
}

function valueOf<T>(result: ExperimentResult<T> | undefined): T {
  if (!result?.ok) throw new Error(`expected a value, got ${JSON.stringify(result)}`)
  return result.value
}

async function measure(points: MetricPoint[]): Promise<Measured> {
  const db = await revision3Database(points)
  const url = 'https://bucket.test/exp.db'
  const { transport, requests } = memoryTransport({ [url]: db })
  const cost = (from: number) => {
    const issued = requests.slice(from)
    return {
      requests: issued.length,
      bytes: issued.reduce((sum, request) => sum + request.length, 0),
    }
  }
  const provider = new ExperimentSnapshotDatabaseProvider({ transport })
  await provider.init({
    modelsInfo: [{ modelId: 'big', source: { kind: 'range', url, offset: 0, size: db.length } }],
  })
  const open = cost(0)

  const afterOpen = requests.length
  const [catalog] = await provider.getMetricCatalogs()
  expect(valueOf(catalog).metrics.map((entry) => entry.count)).toEqual(
    KEYS.map(() => points.length / KEYS.length),
  )
  const catalogCost = cost(afterOpen)

  const afterCatalog = requests.length
  const [buckets] = await provider.getMetricBuckets({ keys: KEYS, ...WINDOW })
  const series = valueOf(buckets).series
  expect(series.map((item) => item.buckets.length)).toEqual(KEYS.map(() => 1000))
  expect(series[0]?.buckets).toEqual(
    oracleBuckets(points, KEYS[0] ?? '', 3, WINDOW.start_step, WINDOW.end_step).map(
      ({ sumAbs: _sumAbs, ...bucket }) => ({
        ...bucket,
        sum: expect.closeTo(bucket.sum ?? 0, 6),
      }),
    ),
  )
  const bucketsCost = cost(afterCatalog)

  const afterBuckets = requests.length
  const [whole] = await provider.getMetricBuckets({ keys: ['lr'], level: 0 })
  expect(whole).toMatchObject({ ok: false, error: { code: TOO_MANY_BUCKETS } })
  const rejected = cost(afterBuckets)

  const fresh = new ExperimentSnapshotDatabaseProvider({ transport })
  await fresh.init({
    modelsInfo: [{ modelId: 'big', source: { kind: 'range', url, offset: 0, size: db.length } }],
  })
  const afterReopen = requests.length
  expect((await fresh.getDynamicMetricsNames()).sort()).toEqual([...KEYS].sort())
  return {
    dbSize: db.length,
    open,
    catalog: catalogCost,
    buckets: bucketsCost,
    rejected,
    names: cost(afterReopen),
  }
}

describe('a range-backed revision 3 experiment reads metadata first and buckets by need', () => {
  let small: Measured
  let large: Measured

  beforeAll(async () => {
    small = await measure(bulkPoints(100_000))
    large = await measure(bulkPoints(400_000))
  }, 120_000)

  // The probe reads the first chunk (header and schema) and seeds the cache with it; the
  // chunks of exp_schema_migrations and exp_schema_info follow in one request.
  it('opens with two requests over three metadata chunks, whatever the size', () => {
    for (const measured of [small, large]) {
      expect(measured.open.requests).toBeLessThanOrEqual(2)
      expect(measured.open.bytes).toBeLessThanOrEqual(3 * CHUNK)
    }
    expect(large.open).toEqual(small.open)
  })

  it('answers the catalog with a few requests that do not grow with the experiment', () => {
    expect(large.dbSize).toBeGreaterThan(3 * small.dbSize)
    for (const measured of [small, large]) {
      expect(measured.catalog.requests).toBeLessThanOrEqual(3)
      expect(measured.catalog.bytes).toBeLessThanOrEqual(3 * CHUNK)
    }
    expect(large.catalog.requests).toBeLessThanOrEqual(small.catalog.requests + 1)
  })

  it('lists metric names from the catalog, without a lookup per key', () => {
    for (const measured of [small, large]) {
      expect(measured.names).toEqual(measured.catalog)
    }
  })

  // 20,001 points of one key, about 600 KB, prove the cap is exceeded; the rest of the key
  // (12 MB in the large experiment) is never read.
  it('rejects a level 0 read of a whole large key after a bounded read', () => {
    for (const measured of [small, large]) {
      expect(measured.rejected.bytes).toBeLessThanOrEqual(2 * 1024 * 1024)
    }
    expect(large.rejected.bytes).toBeLessThanOrEqual(small.rejected.bytes + 2 * CHUNK)
  })

  // The bound depends on the window and the key count only: each key's level-3 rows are one
  // contiguous run, read with at most two requests once runs are too far apart to share one.
  it('reads a stored-level window with a size-independent cost far below the DB size', () => {
    for (const measured of [small, large]) {
      expect(measured.buckets.requests).toBeLessThanOrEqual(2 * KEYS.length)
      expect(measured.buckets.bytes).toBeLessThanOrEqual(KEYS.length * 4 * CHUNK)
      expect(measured.buckets.bytes).toBeLessThan(measured.dbSize / 10)
    }
  })
})

describe('range-backed bucket reads on an expired URL', () => {
  it('reject the whole call so the worker proxy can renew the URL and retry', async () => {
    const db = await revision3Database(bulkPoints(2000))
    const url = 'https://bucket.test/small.db'
    const { transport, controls } = memoryTransport({ [url]: db })
    const provider = new ExperimentSnapshotDatabaseProvider({ transport })
    await provider.init({
      modelsInfo: [
        { modelId: 'small', source: { kind: 'range', url, offset: 0, size: db.length } },
      ],
    })
    controls.failingUrls.add(url)

    const read = provider.getMetricBuckets({ keys: KEYS, level: 0 })
    await expect(read).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
  })
})
