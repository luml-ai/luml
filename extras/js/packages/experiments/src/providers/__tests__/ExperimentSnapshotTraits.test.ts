import { describe, it, expect } from 'vitest'
import { readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { KNOWN_SCHEMA_REVISIONS, readSnapshotTraits } from '../ExperimentSnapshotTraits'
import { memoryDatabase } from './helpers/memoryDatabase'

const SDK_EXP_MIGRATIONS_DIR = resolve(
  __dirname,
  '../../../../../../../sdk/python/sdk/luml/experiments/backends/exp_migrations',
)

const REVISION_2_TABLES = `
  CREATE TABLE static_params (key TEXT, value TEXT, value_type TEXT);
  CREATE TABLE attachments (id TEXT, name TEXT, file_path TEXT, created_at TEXT, size INTEGER);
  CREATE TABLE eval_annotations (id TEXT);
  CREATE TABLE span_annotations (id TEXT);
`

const REVISION_3_TABLES = `
  CREATE TABLE metric_keys (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
  CREATE TABLE metric_points (metric_id INTEGER, step INTEGER, value REAL, logged_ms INTEGER);
  CREATE TABLE metric_buckets (level INTEGER, metric_id INTEGER, bucket INTEGER);
  CREATE TABLE exp_schema_info (key TEXT PRIMARY KEY, value TEXT NOT NULL);
  INSERT INTO exp_schema_info VALUES ('min_reader_revision', '2'), ('min_writer_revision', '3'),
    ('bucket_min_level', '3'), ('bucket_max_level', '12');
`

const SPANS_TABLE = 'CREATE TABLE spans (trace_id TEXT, span_id TEXT);'

const SUMMARY_TABLES = [
  'snapshot_trace_summaries',
  'snapshot_eval_score_stats',
  'snapshot_span_attribute_keys',
  'snapshot_eval_column_keys',
]

describe('readSnapshotTraits', () => {
  it('flags a revision newer than the viewer knows and reads it like the newest known one', async () => {
    const db = await memoryDatabase()
    db.run(`PRAGMA user_version = 5; ${REVISION_2_TABLES} ${REVISION_3_TABLES}`)

    expect(readSnapshotTraits(db)).toEqual({
      revision: 5,
      unknownNewerRevision: true,
      minReaderRevision: 2,
      needsNewerReader: false,
      hasExperimentTables: true,
      hasEvalAnnotations: true,
      hasSpanAnnotations: true,
      metricLayout: 'metric-points',
      bucketLevels: { min: 3, max: 12 },
      structuralTraces: false,
      hasTraceSummaries: false,
      hasScoreStats: false,
      hasKeyCatalogs: false,
    })
  })

  it('reads revision 3 with the metric points layout and its stored bucket levels', async () => {
    const db = await memoryDatabase()
    db.run(`PRAGMA user_version = 3; ${REVISION_2_TABLES} ${REVISION_3_TABLES}`)

    expect(readSnapshotTraits(db)).toMatchObject({
      revision: 3,
      unknownNewerRevision: false,
      needsNewerReader: false,
      metricLayout: 'metric-points',
      bucketLevels: { min: 3, max: 12 },
    })
  })

  it('refuses a DB whose min_reader_revision is above the newest known revision', async () => {
    const db = await memoryDatabase()
    db.run(`PRAGMA user_version = 6; ${REVISION_2_TABLES} ${REVISION_3_TABLES}
      UPDATE exp_schema_info SET value = '5' WHERE key = 'min_reader_revision';`)

    expect(readSnapshotTraits(db)).toEqual({
      revision: 6,
      unknownNewerRevision: true,
      minReaderRevision: 5,
      needsNewerReader: true,
      hasExperimentTables: false,
      hasEvalAnnotations: false,
      hasSpanAnnotations: false,
      metricLayout: 'dynamic-metrics',
      bucketLevels: null,
      structuralTraces: false,
      hasTraceSummaries: false,
      hasScoreStats: false,
      hasKeyCatalogs: false,
    })
  })

  it('prefers the recorded migrations over user_version', async () => {
    const db = await memoryDatabase()
    db.run(`
      PRAGMA user_version = 0;
      ${REVISION_2_TABLES}
      CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
      INSERT INTO exp_schema_migrations (version) VALUES (1), (2);
    `)

    expect(readSnapshotTraits(db)).toMatchObject({ revision: 2, unknownNewerRevision: false })
  })

  it('reads revision 0 for a pre-migration DB without user_version', async () => {
    const db = await memoryDatabase()
    db.run('CREATE TABLE static_params (key TEXT, value TEXT, value_type TEXT)')

    expect(readSnapshotTraits(db)).toEqual({
      revision: 0,
      unknownNewerRevision: false,
      minReaderRevision: 0,
      needsNewerReader: false,
      hasExperimentTables: true,
      hasEvalAnnotations: false,
      hasSpanAnnotations: false,
      metricLayout: 'dynamic-metrics',
      bucketLevels: null,
      structuralTraces: false,
      hasTraceSummaries: false,
      hasScoreStats: false,
      hasKeyCatalogs: false,
    })
  })

  it('reads span trees by structure from revision 3 on, and never before', async () => {
    for (const revision of [0, 1, 2, 3, 4]) {
      const db = await memoryDatabase()
      db.run(`PRAGMA user_version = ${revision}; ${REVISION_2_TABLES} ${SPANS_TABLE}
        ${revision >= 3 ? REVISION_3_TABLES : ''}`)
      expect(readSnapshotTraits(db).structuralTraces).toBe(revision >= 3)
    }
  })

  it('reads no span structure from a revision 3 DB without spans', async () => {
    const db = await memoryDatabase()
    db.run(`PRAGMA user_version = 3; ${REVISION_2_TABLES} ${REVISION_3_TABLES}`)

    expect(readSnapshotTraits(db).structuralTraces).toBe(false)
  })

  it.each([
    [[], { hasTraceSummaries: false, hasScoreStats: false, hasKeyCatalogs: false }],
    [SUMMARY_TABLES, { hasTraceSummaries: true, hasScoreStats: true, hasKeyCatalogs: true }],
    [
      ['snapshot_trace_summaries', 'snapshot_eval_score_stats'],
      { hasTraceSummaries: true, hasScoreStats: true, hasKeyCatalogs: false },
    ],
    [
      ['snapshot_span_attribute_keys'],
      { hasTraceSummaries: false, hasScoreStats: false, hasKeyCatalogs: false },
    ],
    [
      ['snapshot_eval_score_stats', 'snapshot_span_attribute_keys', 'snapshot_eval_column_keys'],
      { hasTraceSummaries: false, hasScoreStats: true, hasKeyCatalogs: true },
    ],
  ])('reads the derived tables %j as present', async (tables, expected) => {
    const db = await memoryDatabase()
    db.run(`PRAGMA user_version = 3; ${REVISION_2_TABLES} ${SPANS_TABLE} ${REVISION_3_TABLES}
      ${tables.map((table) => `CREATE TABLE ${table} (id TEXT);`).join('\n')}`)

    expect(readSnapshotTraits(db)).toMatchObject({ structuralTraces: true, ...expected })
  })

  it('knows every experiment DB migration the SDK ships', () => {
    const migrationRevisions = readdirSync(SDK_EXP_MIGRATIONS_DIR)
      .map((file) => /^(\d+)_.*\.py$/.exec(file)?.[1])
      .filter((revision): revision is string => revision !== undefined)
      .map(Number)

    expect(migrationRevisions.length).toBeGreaterThan(0)
    expect(KNOWN_SCHEMA_REVISIONS).toEqual(expect.arrayContaining(migrationRevisions))
  })
})
