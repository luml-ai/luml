import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import sqlite3InitModule, { type Sqlite3Static } from '@sqlite.org/sqlite-wasm'
import {
  ExperimentSnapshotDatabaseProvider,
  type ExperimentSnapshotModelSource,
} from '../../ExperimentSnapshotDatabaseProvider'
import type { SnapshotTraits } from '../../ExperimentSnapshotTraits'
import type { SnapshotDatabase } from '../../snapshot-source/SnapshotDatabase'
import type { RangeCacheOptions } from '../../snapshot-source/RangeChunkCache'
import { FIXTURES_DIR, indexTar, memoryTransport, readFixtureTar } from './snapshotSources'

export interface FixtureTrace {
  trace_id: string
  span_count: number
  root_span: string
  span_names: string[]
  max_depth: number
  execution_time: number
  state: number
  linked_evals: string[]
  span_types: Record<string, number>
  status_messages: Record<string, string>
  events: Record<string, unknown[]>
  links: Record<string, unknown[]>
}

export interface FixtureDataset {
  eval_ids: string[]
  average_scores: Record<string, number>
  column_keys?: Record<string, Record<string, string>>
  linked: { eval_id: string; trace_id: string } | null
}

export interface TraceFixture {
  snapshot_member: string
  page_size?: number
  expected: {
    traces: FixtureTrace[]
    span_attribute_keys?: Record<string, string>
    datasets: Record<string, FixtureDataset>
    span_annotations: number
    large_attribute?: {
      trace_id: string
      span_id: string
      key: string
      length: number
      sha256: string
    }
  }
}

export function readTraceFixture(name: string): TraceFixture {
  return JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8')) as TraceFixture
}

/** The snapshot DB of a fixture whose member is a plain `exp.db`, and where it sits in the tar. */
export function fixtureDatabase(name: string): { bytes: Uint8Array; offset: number } {
  const tar = readFixtureTar(name)
  const [offset, size] = indexTar(tar)[readTraceFixture(name).snapshot_member]!
  return { bytes: tar.slice(offset, offset + size), offset }
}

/** Opens a fixture as the platform does: range reads for `exp.db`, a download for a zip. */
export async function fixtureProvider(
  name: string,
  cache: Partial<RangeCacheOptions> = {},
): Promise<{
  provider: ExperimentSnapshotDatabaseProvider
  requests: ReturnType<typeof memoryTransport>['requests']
  memberOffset: number
}> {
  const tar = readFixtureTar(name)
  const member = readTraceFixture(name).snapshot_member
  const [offset, size] = indexTar(tar)[member]!
  const url = `fixture:${name}`
  const { transport, requests } = memoryTransport({ [url]: tar })
  const source: ExperimentSnapshotModelSource = member.endsWith('.zip')
    ? { modelId: name, buffer: tar.slice(offset, offset + size).buffer }
    : { modelId: name, source: { kind: 'range', url, offset, size } }
  const provider = new ExperimentSnapshotDatabaseProvider({ transport, raw: { cache } })
  await provider.init({ modelsInfo: [source] })
  return { provider, requests, memberOffset: offset }
}

export async function rawProvider(
  modelId: string,
  bytes: Uint8Array,
): Promise<ExperimentSnapshotDatabaseProvider> {
  const provider = new ExperimentSnapshotDatabaseProvider()
  await provider.init({
    modelsInfo: [{ modelId, source: { kind: 'raw', buffer: bytes.slice().buffer } }],
  })
  return provider
}

interface ProviderInternals {
  _modelsSnapshots: { modelId: string; database: SnapshotDatabase }[]
  snapshotTraits: WeakMap<SnapshotDatabase, SnapshotTraits>
}

export function providerDatabase(provider: ExperimentSnapshotDatabaseProvider): SnapshotDatabase {
  return (provider as unknown as ProviderInternals)._modelsSnapshots[0]!.database
}

export function providerTraits(provider: ExperimentSnapshotDatabaseProvider): SnapshotTraits {
  const internals = provider as unknown as ProviderInternals
  return internals.snapshotTraits.get(providerDatabase(provider))!
}

/** Makes the provider read this snapshot as it reads revisions 0 to 2: today's queries. */
export function useBaseTableReads(provider: ExperimentSnapshotDatabaseProvider): void {
  const internals = provider as unknown as ProviderInternals
  const database = providerDatabase(provider)
  internals.snapshotTraits.set(database, {
    ...internals.snapshotTraits.get(database)!,
    structuralTraces: false,
    hasTraceSummaries: false,
    hasScoreStats: false,
    hasKeyCatalogs: false,
  })
}

/** Records the SQL the provider prepares on its snapshot. */
export function recordSql(provider: ExperimentSnapshotDatabaseProvider): string[] {
  const database = providerDatabase(provider)
  const statements: string[] = []
  const prepare = database.prepare.bind(database)
  const exec = database.exec.bind(database)
  database.prepare = (sql, params) => {
    statements.push(sql)
    return prepare(sql, params)
  }
  database.exec = (sql, params) => {
    statements.push(sql)
    return exec(sql, params)
  }
  return statements
}

export function queryPlan(database: SnapshotDatabase, sql: string, params: (string | number)[]) {
  const statement = database.prepare(`EXPLAIN QUERY PLAN ${sql}`)
  try {
    statement.bind(params)
    const details: string[] = []
    while (statement.step()) details.push(String(statement.get()[3]))
    return details
  } finally {
    statement.free()
  }
}

let sqlite: Promise<Sqlite3Static> | null = null

/** A copy of `bytes` changed by `sql`, as a new snapshot file. */
export async function editedDatabase(bytes: Uint8Array, sql: string): Promise<Uint8Array> {
  sqlite ??= sqlite3InitModule()
  const { capi, wasm, oo1 } = await sqlite
  const db = new oo1.DB(':memory:')
  const pointer = wasm.allocFromTypedArray(bytes)
  const flags = capi.SQLITE_DESERIALIZE_FREEONCLOSE | capi.SQLITE_DESERIALIZE_RESIZEABLE
  if (capi.sqlite3_deserialize(db, 'main', pointer, bytes.length, bytes.length, flags) !== 0) {
    throw new Error('could not load the fixture DB')
  }
  // A fixture written in WAL mode would be read as needing its -wal file.
  db.exec('PRAGMA journal_mode = DELETE')
  db.exec(sql)
  const edited = capi.sqlite3_js_db_export(db)
  db.close()
  return edited
}
