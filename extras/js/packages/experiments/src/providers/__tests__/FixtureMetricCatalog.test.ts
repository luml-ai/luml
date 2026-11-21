import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { MetricCatalogEntry } from '@/metric-buckets/types'
import { FIXTURES_DIR, indexTar, readFixtureTar } from './helpers/snapshotSources'

type StoredValue = number | 'Infinity' | '-Infinity' | null

interface FixtureMetrics {
  snapshot_member: string
  expected: {
    metrics: Record<
      string,
      { count: number; first_step: number; last_step: number; min: number; max: number }
    >
    non_finite_metric: { name: string; stored: { step: number; value: StoredValue }[] } | null
  }
}

const FIXTURES = [
  'a_premigration_legacy_indexes',
  'a_premigration_wal_lost',
  'b_premigration',
  'c_sdk_0_1_0',
  'd_sdk_0_5_0',
  'e_baseline_quirk',
  'f_model_sdk_0_5_0',
  'g_raw_sdk_0_5_0',
  'h_raw_model_sdk_0_5_0',
]

/** Every fixture here is revision 0-2, whose catalog reads only the (key, step) index. */
function expectedCatalog({ expected }: FixtureMetrics): MetricCatalogEntry[] {
  const unknown = { count: null, min: null, max: null }
  const entries: MetricCatalogEntry[] = Object.entries(expected.metrics).map(([key, stats]) => ({
    key,
    first_step: stats.first_step,
    last_step: stats.last_step,
    ...unknown,
  }))
  const nonFinite = expected.non_finite_metric
  if (nonFinite) {
    const steps = nonFinite.stored.map((point) => point.step)
    entries.push({
      key: nonFinite.name,
      first_step: Math.min(...steps),
      last_step: Math.max(...steps),
      ...unknown,
    })
  }
  return entries.sort((left, right) => (left.key < right.key ? -1 : 1))
}

describe.each(FIXTURES)('metric catalog of published fixture %s', (name) => {
  it('summarizes every logged metric', async () => {
    const description = JSON.parse(
      readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8'),
    ) as FixtureMetrics
    const archive = readFixtureTar(name)
    const [offset, size] = indexTar(archive)[description.snapshot_member] ?? [0, 0]
    const buffer = archive.slice(offset, offset + size).buffer
    const provider = new ExperimentSnapshotDatabaseProvider()
    await provider.init({
      modelsInfo: [
        description.snapshot_member.endsWith('.zip')
          ? { modelId: name, buffer }
          : { modelId: name, source: { kind: 'raw', buffer } },
      ],
    })

    const [catalog] = await provider.getMetricCatalogs()
    expect(catalog).toMatchObject({ ok: true, value: { metrics: expectedCatalog(description) } })
  })
})
