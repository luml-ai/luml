import type {
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  GetEvalsByDatasetParams,
  GetTracesParams,
  ModelScores,
  ModelSnapshot,
  ScoreInfo,
  SpansListType,
  SpansParams,
  TraceSpan,
  TypedColumnInfo,
  TypedEvalsColumns,
  TypedTracesColumns,
  ValidateResponseItem,
} from '../interfaces/interfaces'
import { safeParse } from '../helpers/helpers'
import { loadAsync as loadZipAsync } from 'jszip'
import type { Trace } from './ExperimentSnapshotApiProvider.interface'
import {
  type Annotation,
  AnnotationKind,
  type AnnotationSummary,
  AnnotationValueType,
} from '@/components/annotations/annotations.interface'
import { SearchEvalsUtils, SearchTracesUtils } from '@/utils/_search_utils'
import {
  NEWEST_KNOWN_REVISION,
  readSnapshotTraits,
  type SnapshotTraits,
} from './ExperimentSnapshotTraits'
import { readMetricBuckets, readMetricCatalog, readMetricKeys } from './snapshotMetricQueries'
import { SnapshotNeedsNewerReaderError, toExperimentReadError } from '../metric-buckets/errors'
import type {
  ExperimentMetricCatalog,
  ExperimentReadError,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogsRequest,
} from '../metric-buckets/types'
import {
  isSnapshotSourceExpired,
  redactSecrets,
  SnapshotFormatError,
} from './snapshot-source/errors'
import type { SnapshotDatabase as Database, SqlValue } from './snapshot-source/SnapshotDatabase'
import { RangeSqliteEngine } from './snapshot-source/RangeSqliteEngine'
import {
  browserTransport,
  BufferRangeFile,
  type HttpRangeFile,
  type SnapshotTransport,
} from './snapshot-source/httpSource'
import {
  DEFAULT_RAW_SNAPSHOT_OPTIONS,
  openRawSnapshot,
  type ExperimentSnapshotSource,
  type RawSnapshotOptions,
  type SnapshotTransportFallback,
  type SnapshotTransportKind,
} from './snapshot-source/openRawSnapshot'
import { toSourceLocation, type SnapshotSourceRef } from './snapshot-source/sourceLocation'
import type { RangeReadStats } from './snapshot-source/RangeChunkCache'
import {
  assertZipEntryFits,
  ZIP_SNAPSHOT_ENTRY,
  zipEntrySize,
} from './snapshot-source/zipDirectory'

/** An experiment whose snapshot could not be fetched carries the error instead of a source. */
export type ExperimentSnapshotModelSource =
  | { modelId: string; buffer: ArrayBuffer }
  | { modelId: string; source: ExperimentSnapshotSource }
  | { modelId: string; error: ExperimentReadError }

export interface ExperimentSnapshotInitData {
  modelsInfo: ExperimentSnapshotModelSource[]
  sqliteWasmUrl?: string
}

export interface ExperimentSnapshotProviderOptions {
  transport?: SnapshotTransport
  raw?: Partial<RawSnapshotOptions>
}

export interface SnapshotTransportStats extends RangeReadStats {
  modelId: string
  transport: SnapshotTransportKind
}

/** An experiment that did not open; the others opened and work. */
export interface SnapshotOpenFailure {
  modelId: string
  error: ExperimentReadError
}

interface OpenedSnapshot {
  modelId: string
  database: Database
  transport: SnapshotTransportKind
  fallback: SnapshotTransportFallback | null
  rangeFile: HttpRangeFile | null
}

interface SnapshotSourceInfo {
  modelId: string
  source: ExperimentSnapshotSource
}

interface FailedSnapshot {
  modelId: string
  /** Null when the snapshot was never fetched. */
  source: ExperimentSnapshotSource | null
  error: ExperimentReadError
}

function transportOf(source: ExperimentSnapshotSource): SnapshotTransportKind {
  if (source.kind === 'zip') return 'zip-full'
  return source.kind === 'raw' ? 'raw-full' : 'raw-range'
}

function isAbortError(error: unknown): boolean {
  return (error as { name?: unknown } | null)?.name === 'AbortError'
}

const SQLLITE_TYPE_MAP = {
  text: 'string',
  integer: 'number',
  real: 'number',
  true: 'boolean',
  false: 'boolean',
  unknown: 'unknown',
} as const

const ANNOTATION_VALUE_TYPE_MAP = {
  int: 'number',
  bool: 'boolean',
  string: 'string',
} as const

export class ExperimentSnapshotDatabaseProvider implements ExperimentSnapshotProvider {
  private _modelsSnapshots: ModelSnapshot[] | null = null
  private evalsDatasetsRequestParams: Record<string, number> = {}
  private batchEvalsCursors: Record<string, Array<string | null>> = {}
  private tracesRequestParams: Record<string, number> = {}
  private snapshotTraits = new WeakMap<Database, SnapshotTraits>()
  private openedSnapshots: OpenedSnapshot[] = []
  private failedSnapshots = new Map<string, FailedSnapshot>()
  // Experiments in the order init received them; statuses and results follow it.
  private modelOrder: string[] = []
  private engine: RangeSqliteEngine | null = null
  private metricCatalogs = new Map<string, ExperimentMetricCatalog>()
  private readonly transport: SnapshotTransport
  private readonly rawOptions: RawSnapshotOptions

  constructor(options: ExperimentSnapshotProviderOptions = {}) {
    this.transport = options.transport ?? browserTransport
    this.rawOptions = { ...DEFAULT_RAW_SNAPSHOT_OPTIONS, ...options.raw }
  }

  private get modelsSnapshots() {
    if (!this._modelsSnapshots) throw new Error('Models snapshots not initialized')
    return this._modelsSnapshots
  }

  /**
   * Opens every experiment on its own: one that cannot open (too large for the full-download
   * fallback, not a snapshot, a source error) is returned as a failure and reported by its
   * status, while the others open and work. An expired source can be renewed and opened
   * again with `reopenSnapshot`, which leaves the opened ones alone. `signal` stops downloads.
   */
  async init(
    data: ExperimentSnapshotInitData,
    signal?: AbortSignal,
  ): Promise<SnapshotOpenFailure[]> {
    const sources: SnapshotSourceInfo[] = data.modelsInfo.flatMap((info) => {
      if ('error' in info) return []
      const source =
        'source' in info ? info.source : ({ kind: 'zip', buffer: info.buffer } as const)
      return [{ modelId: info.modelId, source }]
    })
    this.engine = sources.length ? await RangeSqliteEngine.load(data.sqliteWasmUrl) : null
    const settled = await Promise.allSettled(sources.map((info) => this.openOne(info, signal)))
    signal?.throwIfAborted()
    this.modelOrder = data.modelsInfo.map(({ modelId }) => modelId)
    this.openedSnapshots = []
    this.failedSnapshots = new Map()
    this.metricCatalogs = new Map()
    for (const info of data.modelsInfo) {
      if ('error' in info) this.recordFailure({ ...info, source: null })
    }
    for (const [index, result] of settled.entries()) {
      const info = sources[index]
      if (!info) continue
      if (result.status === 'fulfilled') this.openedSnapshots.push(result.value)
      else this.recordFailure({ ...info, error: toExperimentReadError(result.reason) })
    }
    this.syncModelsSnapshots()
    return this.openFailures()
  }

  /**
   * Opens one experiment that failed to open from a range source again, from a renewed URL
   * or token; the experiments already open are kept as they are.
   */
  async reopenSnapshot(
    modelId: string,
    location: SnapshotSourceRef,
    signal?: AbortSignal,
  ): Promise<SnapshotOpenFailure[]> {
    const failed = this.failedSnapshots.get(modelId)
    if (failed?.source?.kind !== 'range') {
      throw new Error(`Snapshot '${modelId}' has no range source that failed to open`)
    }
    const { offset, size } = failed.source
    const source = { kind: 'range' as const, offset, size, ...toSourceLocation(location) }
    try {
      const opened = await this.openOne({ modelId, source }, signal)
      this.failedSnapshots.delete(modelId)
      this.openedSnapshots.push(opened)
      this.syncModelsSnapshots()
    } catch (error) {
      if (isAbortError(error)) throw error
      this.recordFailure({ modelId, source, error: toExperimentReadError(error) })
    }
    return this.openFailures()
  }

  private async openOne(
    { modelId, source }: SnapshotSourceInfo,
    signal?: AbortSignal,
  ): Promise<OpenedSnapshot> {
    const engine = this.engine
    if (!engine) throw new Error('SQLite engine not loaded')
    let snapshot: OpenedSnapshot
    if (source.kind === 'zip') {
      const database = await this.openZipSnapshot(engine, modelId, source.buffer)
      snapshot = { modelId, database, transport: 'zip-full', fallback: null, rangeFile: null }
    } else {
      const opened = await openRawSnapshot(
        engine,
        this.transport,
        modelId,
        source,
        this.rawOptions,
        signal,
      )
      snapshot = { modelId, ...opened }
    }
    // Reading the traits reads pages, so a source failure surfaces here, at open.
    try {
      this.snapshotTraits.set(snapshot.database, readSnapshotTraits(snapshot.database))
    } catch (error) {
      snapshot.database.close()
      throw error
    }
    return snapshot
  }

  /** The UI shows only a short text per code, so the message is logged for diagnosis. */
  private recordFailure(failed: FailedSnapshot): void {
    this.failedSnapshots.set(failed.modelId, failed)
    console.warn(
      `Experiment '${failed.modelId}' did not open: ${redactSecrets(failed.error.message)}`,
    )
  }

  private syncModelsSnapshots(): void {
    const order = new Map(this.modelOrder.map((modelId, index) => [modelId, index]))
    this.openedSnapshots.sort(
      (left, right) => (order.get(left.modelId) ?? 0) - (order.get(right.modelId) ?? 0),
    )
    this._modelsSnapshots = this.openedSnapshots.map(({ modelId, database }) => ({
      modelId,
      database,
    }))
  }

  private openFailures(): SnapshotOpenFailure[] {
    return this.modelOrder.flatMap((modelId) => {
      const failed = this.failedSnapshots.get(modelId)
      return failed ? [{ modelId, error: failed.error }] : []
    })
  }

  /** Points a range-backed snapshot at a renewed URL or token. */
  async setSourceUrl(modelId: string, source: SnapshotSourceRef) {
    const snapshot = this.openedSnapshots.find((item) => item.modelId === modelId)
    if (!snapshot?.rangeFile) throw new Error(`Snapshot '${modelId}' is not range-backed`)
    snapshot.rangeFile.location = toSourceLocation(source)
  }

  async getTransportStats(): Promise<SnapshotTransportStats[]> {
    return this.openedSnapshots.map(({ modelId, transport, rangeFile }) => ({
      modelId,
      transport,
      ...(rangeFile?.cache.stats ?? { requests: 0, bytesFetched: 0, cacheHits: 0, cacheMisses: 0 }),
    }))
  }

  async getExperimentStatuses(): Promise<ExperimentSnapshotStatus[]> {
    return this.modelOrder.flatMap((modelId): ExperimentSnapshotStatus[] => {
      const failed = this.failedSnapshots.get(modelId)
      if (failed) {
        return [
          {
            modelId,
            revision: null,
            transport: failed.source ? transportOf(failed.source) : 'raw-range',
            transportFallback: null,
            unknownNewerRevision: false,
            skippedMetricRows: null,
            error: failed.error,
          },
        ]
      }
      const opened = this.openedSnapshots.find((snapshot) => snapshot.modelId === modelId)
      if (!opened) return []
      const { database, transport, fallback, rangeFile } = opened
      const traits = this.traitsOf(database)
      // A storage that stopped honouring Range fails every later read of this experiment.
      const failure = this.readerRefusal(modelId, traits) ?? rangeFile?.failure ?? null
      return [
        {
          modelId,
          revision: traits.revision,
          transport,
          transportFallback: fallback,
          unknownNewerRevision: traits.unknownNewerRevision,
          skippedMetricRows: this.metricCatalogs.get(modelId)?.skipped_rows ?? null,
          error: failure ? toExperimentReadError(failure) : null,
        },
      ]
    })
  }

  /** `refresh` is ignored: a published snapshot never changes, so its cached catalog stays right. */
  async getMetricCatalogs(
    request: MetricCatalogsRequest = {},
    signal?: AbortSignal,
  ): Promise<ExperimentResult<ExperimentMetricCatalog>[]> {
    return this.resultsFor(request.modelIds, signal, (snapshot) => this.catalogOf(snapshot))
  }

  /** One SQL statement per experiment covers every requested key. */
  async getMetricBuckets(
    request: MetricBucketsRequest,
    signal?: AbortSignal,
  ): Promise<ExperimentResult<MetricBucketsResponse>[]> {
    return this.resultsFor(request.modelIds, signal, (snapshot) =>
      readMetricBuckets(
        snapshot.database,
        this.traitsOf(snapshot.database),
        snapshot.modelId,
        this.catalogOf(snapshot),
        request,
      ),
    )
  }

  /** One result per requested experiment; one that did not open answers with its error. */
  private resultsFor<T>(
    modelIds: string[] | undefined,
    signal: AbortSignal | undefined,
    read: (snapshot: ModelSnapshot) => T,
  ): ExperimentResult<T>[] {
    const wanted = modelIds
      ? this.modelOrder.filter((id) => modelIds.includes(id))
      : this.modelOrder
    return wanted.flatMap((modelId): ExperimentResult<T>[] => {
      signal?.throwIfAborted()
      const failed = this.failedSnapshots.get(modelId)
      if (failed) return [{ modelId, ok: false, error: failed.error }]
      const snapshot = this.modelsSnapshots.find((item) => item.modelId === modelId)
      return snapshot ? [this.experimentResult(snapshot, () => read(snapshot))] : []
    })
  }

  private catalogOf(snapshot: ModelSnapshot): ExperimentMetricCatalog {
    let catalog = this.metricCatalogs.get(snapshot.modelId)
    if (!catalog) {
      catalog = readMetricCatalog(snapshot.database, this.traitsOf(snapshot.database))
      this.metricCatalogs.set(snapshot.modelId, catalog)
    }
    return catalog
  }

  private readerRefusal(modelId: string, traits: SnapshotTraits) {
    if (!traits.needsNewerReader) return null
    return new SnapshotNeedsNewerReaderError(
      modelId,
      traits.revision,
      traits.minReaderRevision,
      NEWEST_KNOWN_REVISION,
    )
  }

  /**
   * Turns a failure into that experiment's error. An expired source URL is rethrown: the
   * worker proxy renews it and retries the whole call.
   */
  private experimentResult<T>(snapshot: ModelSnapshot, read: () => T): ExperimentResult<T> {
    const { modelId, database } = snapshot
    try {
      const refusal = this.readerRefusal(modelId, this.traitsOf(database))
      if (refusal) throw refusal
      return { modelId, ok: true, value: read() }
    } catch (error) {
      if (isSnapshotSourceExpired(error)) throw error
      return { modelId, ok: false, error: toExperimentReadError(error) }
    }
  }

  async getDynamicMetricsNames() {
    const names = this.modelsSnapshots.map((snapshot) => this.getModelMetricsNames(snapshot))
    const uniqueNames = new Set<string>(names.flat())
    return [...uniqueNames]
  }

  async getDynamicMetricData(metricName: string) {
    const data = this.modelsSnapshots.map((snapshot) =>
      this.getModelDynamicMetricData(snapshot.database, metricName, snapshot.modelId),
    )
    return data
  }

  async getStaticParamsList() {
    const list = this.modelsSnapshots
      .map((snapshot) => this.getStaticParams(snapshot.database, snapshot.modelId))
      .flat()
    return list
  }

  async getUniqueDatasetsIds(): Promise<string[]> {
    const ids = this.modelsSnapshots.map((snapshot) =>
      this.getUniqueDatasetsIdsByDatabase(snapshot.database),
    )
    const uniqueIds = new Set<string>(ids.flat())
    return [...uniqueIds]
  }

  async getNextEvalsByDatasetId(params: GetEvalsByDatasetParams): Promise<EvalsInfo[]> {
    if (this.modelsSnapshots.length > 1) return this.getNextBatchEvalsByDatasetId(params)
    const keys = this.modelsSnapshots.map((snapshot) =>
      this.getEvalsPageKey(snapshot.modelId, params.dataset_id),
    )
    return this.keepPagingOnFailure(this.evalsDatasetsRequestParams, keys, () =>
      this.getNextSingleEvalsByDatasetId(params),
    )
  }

  private async getNextSingleEvalsByDatasetId(
    params: GetEvalsByDatasetParams,
  ): Promise<EvalsInfo[]> {
    const promises = this.modelsSnapshots.map(async (snapshot) => {
      const key = this.getEvalsPageKey(snapshot.modelId, params.dataset_id)
      const page = this.evalsDatasetsRequestParams[key] || 1
      this.evalsDatasetsRequestParams[key] = page + 1
      const results = await this.getDatabaseEvalsByDatasetId(snapshot.database, {
        ...params,
        page,
        modelId: snapshot.modelId,
      })
      return results
    })
    return this.getFlatPromisesResponse(promises)
  }

  async getFreshEvalsByDatasetId(params: GetEvalsByDatasetParams): Promise<EvalsInfo[]> {
    if (this.modelsSnapshots.length > 1) return this.getFreshBatchEvalsByDatasetId(params)
    const promises = this.modelsSnapshots.map(async (snapshot) => {
      const key = this.getEvalsPageKey(snapshot.modelId, params.dataset_id)
      const page = this.evalsDatasetsRequestParams[key] || 1
      const pagesList = Array.from({ length: Math.max(page - 1, 1) }, (_, i) => i + 1)
      const promises = pagesList.map(async (page) => {
        return this.getDatabaseEvalsByDatasetId(snapshot.database, {
          ...params,
          page,
          modelId: snapshot.modelId,
        })
      })
      return this.getFlatPromisesResponse(promises)
    })
    return this.getFlatPromisesResponse(promises)
  }

  private async getNextBatchEvalsByDatasetId(
    params: GetEvalsByDatasetParams,
  ): Promise<EvalsInfo[]> {
    const cursors = this.batchEvalsCursors[params.dataset_id] || []
    const currentCursor = cursors[cursors.length - 1]
    if (currentCursor === null) return []
    const { items, cursor: newCursor } = await this.getBatchExperimentEvals({
      experiment_ids: this.modelsSnapshots.map((snapshot) => snapshot.modelId),
      limit: params.limit,
      cursor: currentCursor,
      dataset_id: params.dataset_id,
      search: params.search,
      filters: params.filters,
    })
    this.batchEvalsCursors[params.dataset_id] = [...cursors, newCursor]
    return items
  }

  private async getFreshBatchEvalsByDatasetId(
    params: GetEvalsByDatasetParams,
  ): Promise<EvalsInfo[]> {
    const cursors = this.batchEvalsCursors[params.dataset_id] || []
    const cursorsList: Array<string | null> = [null, ...cursors]
    cursorsList.pop()
    const promises = cursorsList.map(async (cursor) => {
      const { items } = await this.getBatchExperimentEvals({
        experiment_ids: this.modelsSnapshots.map((snapshot) => snapshot.modelId),
        limit: params.limit,
        cursor,
        dataset_id: params.dataset_id,
        search: params.search,
        filters: params.filters,
      })
      return items
    })
    return this.getFlatPromisesResponse(promises)
  }

  async getAllDatasetEvals(params: Omit<GetEvalsByDatasetParams, 'limit'>): Promise<EvalsInfo[]> {
    const promises = this.modelsSnapshots.map(async (snapshot) => {
      const results = await this.getDatabaseEvalsByDatasetId(snapshot.database, {
        ...params,
        modelId: snapshot.modelId,
      })
      return results
    })
    return this.getFlatPromisesResponse(promises)
  }

  async getBatchExperimentEvals(params: {
    experiment_ids?: string[]
    limit?: number
    cursor?: string | null
    dataset_id?: string
    search?: string
    filters?: string[]
  }): Promise<{ items: EvalsInfo[]; cursor: string | null }> {
    const limit = params.limit ?? 20
    const snapshots = params.experiment_ids
      ? this.modelsSnapshots.filter((snapshot) => params.experiment_ids!.includes(snapshot.modelId))
      : this.modelsSnapshots

    const { hasMore, pageIds } = this.getBatchPageIds(snapshots, {
      limit,
      cursor: params.cursor,
      dataset_id: params.dataset_id,
      search: params.search,
      filters: params.filters,
    })

    if (!pageIds.length) return { items: [], cursor: null }

    const placeholders = pageIds.map(() => '?').join(', ')
    const query = `
      SELECT id, dataset_id, inputs, outputs, refs, scores, metadata
      FROM evals
      WHERE id IN (${placeholders})
      ORDER BY id
    `

    const snapshotsPromises = snapshots.map(async (snapshot) => {
      if (!this.traitsOf(snapshot.database).hasExperimentTables) return []
      const rows = this._getRowsByQueryAndParams(snapshot.database, query, pageIds)
      const rowsPromises = rows.map(async (row) => {
        const [id, dataset_id, inputs, outputs, refs, scores, metadata] = row
        const annotationsList = await this.getEvalAnnotations(
          snapshot.modelId,
          this.parseValue(dataset_id, 'string'),
          this.parseValue(id, 'string'),
        )
        const annotations = this.annotationsSummary(annotationsList)
        return this.prepareEvalData({
          id,
          dataset_id,
          inputs,
          outputs,
          refs,
          scores,
          metadata,
          modelId: snapshot.modelId,
          annotations,
        })
      })
      return Promise.all(rowsPromises)
    })

    const items = await this.getFlatPromisesResponse(snapshotsPromises)
    items.sort((a, b) => {
      if (a.id !== b.id) return a.id < b.id ? -1 : 1
      if (a.modelId !== b.modelId) return a.modelId < b.modelId ? -1 : 1
      return 0
    })

    const cursor = hasMore ? (pageIds[pageIds.length - 1] ?? null) : null
    return { items, cursor }
  }

  async resetEvalsDatasetsRequestParams() {
    this.evalsDatasetsRequestParams = {}
    this.batchEvalsCursors = {}
  }

  async resetDatasetPage(datasetId: string) {
    for (const snapshot of this.modelsSnapshots) {
      delete this.evalsDatasetsRequestParams[this.getEvalsPageKey(snapshot.modelId, datasetId)]
    }
    delete this.batchEvalsCursors[datasetId]
  }

  /**
   * A failed read is retried by the caller, so it must not advance its page cursors. Only the
   * read's own `keys` are restored: reads of other datasets may run between its awaits.
   */
  private async keepPagingOnFailure<T>(
    pages: Record<string, number>,
    keys: string[],
    read: () => Promise<T>,
  ): Promise<T> {
    const saved = keys.map((key) => [key, pages[key]] as const)
    try {
      return await read()
    } catch (error) {
      for (const [key, page] of saved) {
        if (page === undefined) delete pages[key]
        else pages[key] = page
      }
      throw error
    }
  }

  /** Null for an experiment that failed to open: its status already reports it. */
  private openedDatabase(modelId: string): Database | null {
    const database = this.modelsSnapshots.find((snapshot) => snapshot.modelId === modelId)?.database
    if (database) return database
    if (this.failedSnapshots.has(modelId)) return null
    throw new Error('Database not found')
  }

  private getEvalsPageKey(modelId: string, datasetId: string) {
    return `${modelId}:${datasetId}`
  }

  async getTraceSpans(modelId: string, traceId: string) {
    const db = this.openedDatabase(modelId)
    if (!db || !this.traitsOf(db).hasExperimentTables) return []
    const stmt = db.prepare(`
      SELECT trace_id, span_id, parent_span_id, name, kind,
             start_time_unix_nano, end_time_unix_nano,
             status_code, status_message,
             attributes, events, links, dfs_span_type
      FROM spans
      WHERE trace_id = ?
    `)
    const rows = []
    stmt.bind([traceId])
    while (stmt.step()) {
      const row = stmt.getAsObject()
      const annotationCount = this.getSnapAnnotationsCountByDatabase(db, row.span_id as string)
      const parsedRow = {
        ...row,
        attributes: safeParse(row.attributes as SqlValue),
        events: safeParse(row.events as SqlValue),
        links: safeParse(row.links as SqlValue),
        annotation_count: annotationCount,
      }
      rows.push(parsedRow)
    }
    stmt.free()
    return rows as unknown as SpansListType
  }

  async getTraceId(args: SpansParams) {
    const db = this.openedDatabase(args.modelId)
    if (!db || !this.traitsOf(db).hasExperimentTables) return null
    const rows = this._getRowsByQueryAndParams(
      db,
      'SELECT trace_id FROM eval_traces_bridge WHERE eval_dataset_id = ? AND eval_id = ? LIMIT 1',
      [args.datasetId, args.evalId],
    )
    return rows[0]?.[0] ?? null
  }

  async buildSpanTree(spans: Omit<TraceSpan, 'children'>[]): Promise<TraceSpan[]> {
    const spanMap: Record<string, TraceSpan> = {}
    spans.forEach((span) => {
      spanMap[span.span_id] = { ...span, children: [] }
    })
    const roots: TraceSpan[] = []
    for (const span of Object.values(spanMap)) {
      if (span.parent_span_id) {
        const parent = spanMap[span.parent_span_id]
        if (parent) {
          parent.children!.push(span)
        } else {
          roots.push(span)
        }
      } else {
        roots.push(span)
      }
    }
    return this.sortSpans(roots)
  }

  async getEvalsColumns(datasetId: string): Promise<TypedEvalsColumns> {
    const result = this.modelsSnapshots.reduce(
      (acc, snapshot) => {
        const array = [
          {
            name: 'inputs',
            list: this.extractEvalColumns(snapshot.database, 'inputs', datasetId),
          },
          {
            name: 'outputs',
            list: this.extractEvalColumns(snapshot.database, 'outputs', datasetId),
          },
          {
            name: 'refs',
            list: this.extractEvalColumns(snapshot.database, 'refs', datasetId),
          },
          {
            name: 'scores',
            list: this.extractEvalColumns(snapshot.database, 'scores', datasetId),
          },
          {
            name: 'metadata',
            list: this.extractEvalColumns(snapshot.database, 'metadata', datasetId),
          },
          {
            name: 'annotations_feedback',
            list: this.getAnnotationFields(snapshot.database, datasetId, AnnotationKind.FEEDBACK),
          },
          {
            name: 'annotations_expectations',
            list: this.getAnnotationFields(
              snapshot.database,
              datasetId,
              AnnotationKind.EXPECTATION,
            ),
          },
        ]
        array.forEach((item) => {
          item.list.forEach((column) => {
            const columnExists = acc[item.name as keyof typeof acc].find(
              (existingColumn) => existingColumn.name === column.name,
            )
            if (!columnExists) {
              acc[item.name as keyof typeof acc].push(column)
            }
          })
        })
        return acc
      },
      {
        inputs: new Array<TypedColumnInfo>(),
        outputs: new Array<TypedColumnInfo>(),
        refs: new Array<TypedColumnInfo>(),
        scores: new Array<TypedColumnInfo>(),
        metadata: new Array<TypedColumnInfo>(),
        annotations_feedback: new Array<TypedColumnInfo>(),
        annotations_expectations: new Array<TypedColumnInfo>(),
      },
    )
    return result
  }

  async getDatasetAverageScores(
    datasetId: string,
    search?: string,
    filters?: string[],
  ): Promise<ModelScores[]> {
    return this.modelsSnapshots.map((snapshot) => {
      const traits = this.traitsOf(snapshot.database)
      if (!traits.hasExperimentTables) return { modelId: snapshot.modelId, scores: [] }
      const { whereParts, params } = this.buildEvalsWhere(traits, undefined, search, filters)
      const rows = this._getRowsByQueryAndParams(
        snapshot.database,
        `SELECT scores FROM evals WHERE ${['scores IS NOT NULL', 'dataset_id = ?', ...whereParts].join(' AND ')}`,
        [datasetId, ...params],
      )
      const formattedRows = rows.map((row) => safeParse(row[0] as SqlValue))
      const sum: Record<string, { sum: number; count: number }> = formattedRows.reduce(
        (acc, row) => {
          for (const key in row) {
            const scoreValue = row[key]
            const scoreType = typeof scoreValue
            const availableTypes = ['number', 'boolean']
            const isAvailableType = availableTypes.includes(scoreType)
            if (!isAvailableType) continue
            if (!acc[key]) {
              acc[key] = { sum: 0, count: 0 }
            }
            if (typeof scoreValue === 'number') {
              acc[key].sum += scoreValue
              acc[key].count++
            } else if (typeof scoreValue === 'boolean') {
              acc[key].sum += scoreValue ? 1 : 0
              acc[key].count++
            }
          }
          return acc
        },
        {},
      )
      const entries = Object.entries(sum)
      const scores: ScoreInfo[] = entries.map(([scoreName, { sum, count }]) => {
        return {
          name: scoreName,
          value: sum / count,
        }
      })
      return {
        modelId: snapshot.modelId,
        scores,
      }
    })
  }

  async getEvalAnnotations(artifactId: string, datasetId: string, evalId: string) {
    const db = this.openedDatabase(artifactId)
    if (!db || !this.traitsOf(db).hasEvalAnnotations) return []
    const rows = this._getRowsByQueryAndParams(
      db,
      `
      SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
      FROM eval_annotations
      WHERE eval_id = ? AND dataset_id = ?
      `,
      [evalId, datasetId],
    )
    return rows.map((row) => this.annotationFullData(row))
  }

  async getEvalsDatasetAnnotationsSummary(datasetId: string) {
    const snapshotsPromises = this.modelsSnapshots.map(async (snapshot) => {
      const database = snapshot.database
      const artifactId = snapshot.modelId
      const evalsIds = this.getEvalsIdsByDatabase(database, datasetId)
      const promises = evalsIds.map(async (evalId) => {
        return this.getEvalAnnotations(artifactId, datasetId, evalId)
      })
      return this.getFlatPromisesResponse(promises)
    })
    const annotations = await this.getFlatPromisesResponse(snapshotsPromises)
    return this.annotationsSummary(annotations)
  }

  async getTraces(params: GetTracesParams) {
    const keys = this.modelsSnapshots.map((snapshot) => snapshot.modelId)
    return this.keepPagingOnFailure(this.tracesRequestParams, keys, async () =>
      this.getNextTraces(params),
    )
  }

  private getNextTraces(params: GetTracesParams) {
    const tracesByArtifacts = this.modelsSnapshots.map((snapshot) => {
      const page = this.tracesRequestParams[snapshot.modelId] || 1
      this.tracesRequestParams[snapshot.modelId] = page + 1
      const artifactTraces = this.getTracesByDatabase(snapshot.database, {
        ...params,
        page,
      })
      return artifactTraces
    })
    return tracesByArtifacts.flat()
  }

  async getFreshTraces(params: GetTracesParams) {
    const responses = this.modelsSnapshots.map(async (snapshot) => {
      const page = this.tracesRequestParams[snapshot.modelId] || 1
      const pagesList = Array.from({ length: Math.max(page - 1, 1) }, (_, i) => i + 1)
      const promises = pagesList.map(async (page) => {
        return this.getTracesByDatabase(snapshot.database, {
          ...params,
          page,
        })
      })
      return this.getFlatPromisesResponse(promises)
    })
    return this.getFlatPromisesResponse(responses)
  }

  async getAllTraces(params: Omit<GetTracesParams, 'limit'>): Promise<Trace[]> {
    const tracesByArtifacts = this.modelsSnapshots.map((snapshot) => {
      const artifactTraces = this.getTracesByDatabase(snapshot.database, {
        ...params,
      })
      return artifactTraces
    })
    return tracesByArtifacts.flat()
  }

  async getEvalById(artifactId: string, evalId: string): Promise<EvalsInfo> {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === artifactId)?.database
    if (!db) throw new Error('Database not found')
    const rows = this.traitsOf(db).hasExperimentTables
      ? this._getRowsByQueryAndParams(
          db,
          'SELECT id, dataset_id, inputs, outputs, refs, scores, metadata FROM evals WHERE id = ?',
          [evalId],
        )
      : []
    const row = rows[0]
    if (!row) throw new Error('Eval not found')
    const [id, dataset_id, inputs, outputs, refs, scores, metadata] = row
    const annotationsList = await this.getEvalAnnotations(
      artifactId,
      this.parseValue(dataset_id, 'string'),
      evalId,
    )
    const annotations = this.annotationsSummary(annotationsList)
    return this.prepareEvalData({
      id,
      dataset_id,
      inputs,
      outputs,
      refs,
      scores,
      metadata,
      modelId: artifactId,
      annotations,
    })
  }

  async resetTracesRequestParams(artifactId?: string) {
    if (artifactId) {
      delete this.tracesRequestParams[artifactId]
    } else {
      this.tracesRequestParams = {}
    }
  }

  async getSpanAnnotations(
    artifactId: string,
    traceId: string,
    spanId: string,
  ): Promise<Annotation[]> {
    const db = this.openedDatabase(artifactId)
    if (!db || !this.traitsOf(db).hasSpanAnnotations) return []
    const rows = this._getRowsByQueryAndParams(
      db,
      'SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale FROM span_annotations WHERE trace_id = ? AND span_id = ?',
      [traceId, spanId],
    )
    return rows.map((row) => {
      const [id, name, annotation_kind, value, user, value_type, created_at, rationale] = row
      return {
        id: this.parseValue(id, 'string'),
        name: this.parseValue(name, 'string'),
        annotation_kind: this.parseValue(annotation_kind, 'string'),
        value_type: this.parseValue(value_type, 'string') as AnnotationValueType,
        value: value as number | boolean | string,
        user: this.parseValue(user, 'string'),
        created_at: this.parseValue(created_at, 'string'),
        rationale: this.parseValue(rationale, 'string'),
      }
    })
  }

  async getTracesAnnotationSummary(artifactId: string) {
    const db = this.openedDatabase(artifactId)
    if (!db || !this.traitsOf(db).hasSpanAnnotations) return { feedback: [], expectations: [] }
    const queryResult = db.exec(
      `SELECT name, value, annotation_kind, value_type FROM span_annotations`,
    )
    const rows = queryResult[0]?.values || []
    const annotations = rows.map((row) =>
      this.annotationsData({
        name: row[0],
        value: row[1],
        annotation_kind: row[2],
        value_type: row[3],
      }),
    )
    const summary = this.annotationsSummary(annotations)
    return summary
  }

  async getTracesColumns(artifactId: string): Promise<TypedTracesColumns> {
    const database = this.openedDatabase(artifactId)
    if (!database || !this.traitsOf(database).hasExperimentTables) {
      return { attributes: [], annotations_feedback: [], annotations_expectations: [] }
    }
    const queryResult = database.exec(`
        SELECT je.key, je.type
        FROM spans, json_each(spans.attributes) AS je
        WHERE spans.attributes IS NOT NULL
        GROUP BY je.key
        ORDER BY je.key
    `)
    const values = queryResult[0]?.values || []
    const columns = values.map((value) => {
      const [key, type] = value
      const name = this.parseValue(key, 'string')
      const stringType = this.parseValue(type, 'string')
      const formattedType = this.getSqliteType(stringType)
      return {
        name,
        type: formattedType,
      }
    })
    return {
      attributes: columns,
      annotations_feedback: this.getSpanAnnotationFields(database, AnnotationKind.FEEDBACK),
      annotations_expectations: this.getSpanAnnotationFields(database, AnnotationKind.EXPECTATION),
    }
  }

  async validateEvalsFilter(filters: string[]): Promise<ValidateResponseItem[]> {
    const results = []
    for (const filter of filters) {
      try {
        SearchEvalsUtils.validateFilterString(filter)
        results.push({ valid: true, error: null })
      } catch (error) {
        results.push({
          valid: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        })
      }
    }
    return results
  }

  async validateTracesFilter(filters: string[]): Promise<ValidateResponseItem[]> {
    const results = []
    for (const filter of filters) {
      try {
        SearchTracesUtils.validateFilterString(filter)
        results.push({ valid: true, error: null })
      } catch (error) {
        results.push({
          valid: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        })
      }
    }
    return results
  }

  private sortSpans(tree: TraceSpan[]): TraceSpan[] {
    return tree
      .sort((a, b) => {
        return a.start_time_unix_nano - b.start_time_unix_nano
      })
      .map((span) => {
        return {
          ...span,
          children: this.sortSpans(span.children),
        }
      })
  }

  private getTracesByDatabase(
    database: Database,
    params: Omit<GetTracesParams, 'limit'> & { page?: number; limit?: number },
  ): Trace[] {
    const traits = this.traitsOf(database)
    if (!traits.hasExperimentTables) return []
    const offset = params.page && params.limit ? (params.page - 1) * params.limit : 0
    const limitQuery = params.limit ? 'LIMIT ?' : ''
    const offsetQuery = offset ? 'OFFSET ?' : ''
    const sortBy = ['created_at', 'execution_time', 'span_count'].find(
      (column) => column === params.sort_by,
    )
    if (!sortBy) throw new Error('Invalid trace sort column')
    const safeOrder = params.order?.toLowerCase() === 'asc' ? 'ASC' : 'DESC'

    const whereParts: string[] = []
    const whereParams: SqlValue[] = []
    const havingParts: string[] = []
    const havingParams: SqlValue[] = []

    if (params.search) {
      whereParts.push(`trace_id LIKE ?`)
      whereParams.push(`%${params.search}%`)
    }

    for (const filter of params.filters || []) {
      const [sql, filterParams] = SearchTracesUtils.toSql(filter, traits.hasSpanAnnotations)
      if (!sql) continue

      if (SearchTracesUtils.isAggregateFilter(filter)) {
        havingParts.push(sql)
        havingParams.push(...(filterParams as SqlValue[]))
      } else {
        whereParts.push(sql)
        whereParams.push(...(filterParams as SqlValue[]))
      }
    }

    const whereCondition = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''
    const havingCondition = havingParts.length ? `HAVING ${havingParts.join(' AND ')}` : ''

    const query = `
      SELECT
        trace_id,
        (MAX(end_time_unix_nano) - MIN(start_time_unix_nano)) AS execution_time,
        COUNT(*) AS span_count,
        MIN(created_at) AS created_at,
        CASE
          WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) IS NULL THEN 3
          WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 2 THEN 2
          WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 1 THEN 1
          ELSE 0
        END AS state
      FROM spans
      ${whereCondition}
      GROUP BY trace_id
      ${havingCondition}
      ORDER BY ${sortBy} ${safeOrder}
      ${limitQuery}
      ${offsetQuery}
    `

    const queryParams = [...whereParams, ...havingParams]
    if (params.limit) queryParams.push(params.limit)
    if (offset) queryParams.push(offset)
    const rows = this._getRowsByQueryAndParams(database, query, queryParams)

    return rows.map((row) => {
      const [trace_id, execution_time, span_count, created_at, state] = row
      const traceId = this.parseValue(trace_id, 'string')
      const evals = this.getEvalsByTraceId(database, traceId)
      return {
        trace_id: traceId,
        execution_time: this.parseValue(execution_time, 'float'),
        span_count: this.parseValue(span_count, 'int'),
        created_at: this.parseValue(created_at, 'string'),
        state: this.parseValue(state, 'int'),
        evals,
        annotations: this.getTraceAnnotations(database, traceId),
      }
    })
  }

  private getEvalsByTraceId(database: Database, traceId: string): string[] {
    const rows = this._getRowsByQueryAndParams(
      database,
      'SELECT eval_id FROM eval_traces_bridge WHERE trace_id = ?',
      [traceId],
    )
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private getModelDynamicMetricData(database: Database, metricName: string, modelId: string) {
    const rows = this.traitsOf(database).hasExperimentTables
      ? this._getRowsByQueryAndParams(
          database,
          'SELECT value, step FROM dynamic_metrics WHERE key = ? ORDER BY step ASC',
          [metricName],
        )
      : []
    const total = rows.length
    const MAX_POINTS = 50_000
    const data: ExperimentSnapshotDynamicMetric = {
      x: [],
      y: [],
      modelId,
      aggregated: rows.length > MAX_POINTS,
    }
    if (total === 0) return data
    const stepSize = total > MAX_POINTS ? Math.ceil(total / MAX_POINTS) : 1
    for (let i = 0; i < total; i += stepSize) {
      const row = rows[i]
      const value = row?.[0]
      const step = row?.[1]
      if (typeof step !== 'number' || typeof value !== 'number') continue
      data.x.push(step)
      data.y.push(value)
    }
    return data
  }

  private getDatabaseEvalsByDatasetId(
    database: Database,
    {
      limit,
      sort_by = 'created_at',
      order = 'desc',
      dataset_id,
      search = '',
      filters = [],
      page,
      modelId,
    }: {
      page?: number
      modelId: string
    } & GetEvalsByDatasetParams,
  ) {
    const traits = this.traitsOf(database)
    if (!traits.hasExperimentTables) return []
    const parentColumnsSort = ['created_at', 'id']
    const sortBy = parentColumnsSort.includes(sort_by)
      ? sort_by
      : 'COALESCE(json_extract(scores, ?), 0)'
    const safeOrder = order?.toLowerCase() === 'asc' ? 'ASC' : 'DESC'
    const limitQuery = limit ? 'LIMIT ?' : ''
    const offset = page && limit ? (page - 1) * limit : 0
    const offsetQuery = offset ? 'OFFSET ?' : ''

    const { whereParts, params } = this.buildEvalsWhere(traits, dataset_id, search, filters)
    if (!parentColumnsSort.includes(sort_by)) params.push(`$.${sort_by}`)
    if (limit) params.push(limit)
    if (offset) params.push(offset)

    const whereCondition = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''

    const query = `
      SELECT id, dataset_id, inputs, outputs, refs, scores, metadata
      FROM evals
      ${whereCondition}
      ORDER BY ${sortBy} ${safeOrder}
      ${limitQuery}
      ${offsetQuery}
    `

    const rows = this._getRowsByQueryAndParams(database, query, params)

    const promises = rows.map(async (row) => {
      const [id, dataset_id, inputs, outputs, refs, scores, metadata] = row
      const annotationsList = await this.getEvalAnnotations(
        modelId,
        this.parseValue(dataset_id, 'string'),
        this.parseValue(id, 'string'),
      )
      const annotations = this.annotationsSummary(annotationsList)
      return this.prepareEvalData({
        id,
        dataset_id,
        inputs,
        outputs,
        refs,
        scores,
        metadata,
        modelId,
        annotations,
      })
    })
    return Promise.all(promises)
  }

  private buildEvalsWhere(
    traits: SnapshotTraits,
    dataset_id?: string,
    search?: string,
    filters?: string[],
  ): { whereParts: string[]; params: SqlValue[] } {
    const whereParts: string[] = []
    const params: SqlValue[] = []

    if (dataset_id) {
      whereParts.push(`dataset_id = ?`)
      params.push(dataset_id)
    }

    if (search) {
      const searchWhere = `(id LIKE ?
        OR EXISTS (SELECT 1 FROM json_each(COALESCE(inputs, '{}')) WHERE type = 'text' AND value LIKE ?)
        OR EXISTS (SELECT 1 FROM json_each(COALESCE(outputs, '{}')) WHERE type = 'text' AND value LIKE ?)
        OR EXISTS (SELECT 1 FROM json_each(COALESCE(refs, '{}')) WHERE type = 'text' AND value LIKE ?)
        OR EXISTS (SELECT 1 FROM json_each(COALESCE(scores, '{}')) WHERE type = 'text' AND value LIKE ?)
        OR EXISTS (SELECT 1 FROM json_each(COALESCE(metadata, '{}')) WHERE type = 'text' AND value LIKE ?)
      )`
      const like = `%${search}%`
      whereParts.push(searchWhere)
      params.push(like, like, like, like, like, like)
    }

    for (const filter of filters || []) {
      const [where, filterParams] = SearchEvalsUtils.toSql(filter, traits.hasEvalAnnotations)
      if (where) {
        whereParts.push(where)
        params.push(...(filterParams as SqlValue[]))
      }
    }

    return { whereParts, params }
  }

  private getBatchPageIds(
    snapshots: ModelSnapshot[],
    {
      limit,
      cursor,
      dataset_id,
      search,
      filters,
    }: {
      limit: number
      cursor?: string | null
      dataset_id?: string
      search?: string
      filters?: string[]
    },
  ): { hasMore: boolean; pageIds: string[] } {
    const candidateIds = new Set<string>()

    for (const snapshot of snapshots) {
      const traits = this.traitsOf(snapshot.database)
      if (!traits.hasExperimentTables) continue
      const { whereParts, params } = this.buildEvalsWhere(traits, dataset_id, search, filters)

      if (cursor) {
        whereParts.push(`id > ?`)
        params.push(cursor)
      }

      const whereCondition = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''
      const query = `SELECT id FROM evals ${whereCondition} ORDER BY id LIMIT ?`
      const rows = this._getRowsByQueryAndParams(snapshot.database, query, [...params, limit + 1])
      for (const row of rows) {
        candidateIds.add(this.parseValue(row[0], 'string'))
      }
    }

    const sortedIds = [...candidateIds].sort()
    const hasMore = sortedIds.length > limit
    return { hasMore, pageIds: sortedIds.slice(0, limit) }
  }

  private prepareEvalData({
    id,
    dataset_id,
    inputs,
    outputs,
    refs,
    scores,
    metadata,
    modelId,
    annotations,
  }: {
    id: SqlValue | undefined
    dataset_id: SqlValue | undefined
    inputs: SqlValue | undefined
    outputs: SqlValue | undefined
    refs: SqlValue | undefined
    scores: SqlValue | undefined
    metadata: SqlValue | undefined
    modelId: string
    annotations: AnnotationSummary | null
  }) {
    return {
      id: id?.toString() ?? '',
      dataset_id: dataset_id?.toString() ?? '',
      inputs: safeParse(inputs) || {},
      outputs: safeParse(outputs) || {},
      refs: safeParse(refs) || {},
      scores: safeParse(scores) || {},
      metadata: safeParse(metadata) || {},
      modelId: modelId,
      annotations,
    }
  }

  private extractEvalColumns(
    database: Database,
    column: 'inputs' | 'outputs' | 'refs' | 'scores' | 'metadata',
    datasetId: string,
  ) {
    if (!this.traitsOf(database).hasExperimentTables) return []
    const rows = this._getRowsByQueryAndParams(
      database,
      `
      SELECT je.key, je.type
      FROM evals, json_each(evals.${column}) AS je
      WHERE evals.${column} IS NOT NULL AND evals.dataset_id = ?
      GROUP BY je.key
      ORDER BY je.key
      `,
      [datasetId],
    )
    return rows.map((row) => {
      const [key, type] = row
      const name = this.parseValue(key, 'string')
      const stringType = this.parseValue(type, 'string')
      const formattedType = this.getSqliteType(stringType)
      return {
        name,
        type: formattedType,
      }
    })
  }

  private getUniqueDatasetsIdsByDatabase(database: Database): string[] {
    if (!this.traitsOf(database).hasExperimentTables) return []
    const queryResult = database.exec('SELECT DISTINCT dataset_id FROM evals')
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private parseValue(val: any, type: SqlValue | 'json' | 'int' | 'float' | 'bool') {
    if (type === 'json') return JSON.parse(val)
    if (type === 'int') return parseInt(val)
    if (type === 'float') return parseFloat(val)
    if (type === 'bool') return String(val).toLowerCase() === 'true'
    return val
  }

  private getStaticParams(database: Database, modelId: string): ExperimentSnapshotStaticParams[] {
    const queryResult = this.traitsOf(database).hasExperimentTables
      ? database.exec('SELECT key, value, value_type FROM static_params')
      : []
    const rows = queryResult[0]?.values || []
    const obj = Object.fromEntries(
      rows.map((row) => [row[0], this.parseValue(row[1], row[2] as SqlValue)]),
    )
    return { ...obj, modelId }
  }

  /** On revision 3 the catalog already holds the keys, so no per-key point lookup is made. */
  private getModelMetricsNames(snapshot: ModelSnapshot) {
    const traits = this.traitsOf(snapshot.database)
    if (traits.metricLayout === 'metric-points' && traits.bucketLevels) {
      return this.catalogOf(snapshot).metrics.map((entry) => entry.key)
    }
    return readMetricKeys(snapshot.database, traits)
  }

  /**
   * Zipped snapshots of the first generation keep their WAL-mode header. They are opened like
   * sql.js opened them: main file only, no `-wal`, so the WAL header check does not apply.
   */
  private async openZipSnapshot(engine: RangeSqliteEngine, modelId: string, buffer: ArrayBuffer) {
    const zipBytes = new Uint8Array(buffer)
    assertZipEntryFits(modelId, zipEntrySize(zipBytes, zipBytes.length, ZIP_SNAPSHOT_ENTRY))
    const zip = await loadZipAsync(buffer)
    const dbFile = zip.file(ZIP_SNAPSHOT_ENTRY)
    if (!dbFile) throw new SnapshotFormatError(modelId, 'exp.db not found')
    const content = await dbFile.async('uint8array')
    return engine.openDatabase(new BufferRangeFile(content))
  }

  private traitsOf(database: Database): SnapshotTraits {
    let traits = this.snapshotTraits.get(database)
    if (!traits) {
      traits = readSnapshotTraits(database)
      this.snapshotTraits.set(database, traits)
    }
    return traits
  }

  private getTraceAnnotations(database: Database, traceId: string) {
    if (!this.traitsOf(database).hasSpanAnnotations) return { feedback: [], expectations: [] }
    const rows = this._getRowsByQueryAndParams(
      database,
      `
      SELECT name, value, annotation_kind, value_type
      FROM span_annotations
      WHERE trace_id = ?
      ORDER BY name
    `,
      [traceId],
    )
    const annotations = rows.map((row) =>
      this.annotationsData({
        name: row[0],
        value: row[1],
        value_type: row[3],
        annotation_kind: row[2],
      }),
    )
    return this.annotationsSummary(annotations)
  }

  private formattedAnnotationValue(value: SqlValue | undefined, value_type: AnnotationValueType) {
    if (value_type === AnnotationValueType.INT) return this.parseValue(value, 'int')
    if (value_type === AnnotationValueType.BOOL) return this.parseValue(value, 'bool')
    return this.parseValue(value, 'string')
  }

  private annotationsData(data: {
    name: SqlValue | undefined
    value: SqlValue | undefined
    value_type: SqlValue | undefined
    annotation_kind: SqlValue | undefined
  }) {
    const formattedValue = this.formattedAnnotationValue(
      data.value,
      data.value_type as AnnotationValueType,
    )
    return {
      name: this.parseValue(data.name, 'string'),
      value: formattedValue,
      annotation_kind: this.parseValue(data.annotation_kind, 'string'),
      value_type: this.parseValue(data.value_type, 'string') as AnnotationValueType,
    }
  }

  private annotationFullData(row: SqlValue[]): Annotation {
    const [id, name, annotation_kind, value, user, value_type, created_at, rationale] = row
    return {
      id: this.parseValue(id, 'string'),
      name: this.parseValue(name, 'string'),
      annotation_kind: this.parseValue(annotation_kind, 'string'),
      value_type: this.parseValue(value_type, 'string') as AnnotationValueType,
      value: this.formattedAnnotationValue(value, value_type as AnnotationValueType),
      user: this.parseValue(user, 'string'),
      created_at: this.parseValue(created_at, 'string'),
      rationale: this.parseValue(rationale, 'string'),
    }
  }

  private annotationsSummary(
    annotations: {
      name: string
      value: string | number | boolean
      value_type: AnnotationValueType
      annotation_kind: AnnotationKind
    }[],
  ): AnnotationSummary {
    const results = annotations.reduce(
      (acc, annotation) => {
        if (annotation.annotation_kind === AnnotationKind.FEEDBACK) {
          const current = acc.feedback[annotation.name] || { total: 0, counts: {} }
          current.total++
          const key = annotation.value ? 'true' : 'false'
          const currentCount = current.counts[key] || 0
          current.counts[key] = currentCount + 1
          acc.feedback[annotation.name] = current
        } else {
          const current = acc.expectations[annotation.name] || {
            total: 0,
            positive: 0,
            negative: 0,
            value: null,
          }
          current.total++
          if (annotation.value === true) {
            current.positive++
          } else if (annotation.value === false) {
            current.negative++
          } else if (current.value === null) {
            current.value = annotation.value
          }
          acc.expectations[annotation.name] = current
        }
        return acc
      },
      { feedback: {}, expectations: {} } as {
        feedback: { [key: string]: { total: number; counts: { [key: string]: number } } }
        expectations: {
          [key: string]: {
            total: number
            positive: number
            negative: number
            value: string | number | null
          }
        }
      },
    )
    return {
      feedback: Object.entries(results.feedback).map(([name, data]) => ({
        name,
        ...data,
      })),
      expectations: Object.entries(results.expectations).map(([name, data]) => ({
        name,
        ...data,
      })),
    }
  }

  private getEvalsIdsByDatabase(database: Database, datasetId: string) {
    if (!this.traitsOf(database).hasExperimentTables) return []
    const rows = this._getRowsByQueryAndParams(
      database,
      'SELECT id FROM evals WHERE dataset_id = ?',
      [datasetId],
    )
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private async getFlatPromisesResponse<T>(promises: Promise<T[]>[]): Promise<T[]> {
    const results = await Promise.all(promises)
    return results.flat()
  }

  private getSnapAnnotationsCountByDatabase(database: Database, spanId: string): number {
    if (!this.traitsOf(database).hasSpanAnnotations) return 0
    const rows = this._getRowsByQueryAndParams(
      database,
      'SELECT COUNT(*) FROM span_annotations WHERE span_id = ?',
      [spanId],
    )
    const count = rows[0]?.[0]
    return this.parseValue(count, 'int')
  }

  private getSqliteType(type: string): (typeof SQLLITE_TYPE_MAP)[keyof typeof SQLLITE_TYPE_MAP] {
    return SQLLITE_TYPE_MAP[type as keyof typeof SQLLITE_TYPE_MAP] || 'unknown'
  }

  private _getRowsByQueryAndParams(database: Database, query: string, params: SqlValue[]): any[] {
    const stmt = database.prepare(query)
    try {
      stmt.bind(params)
      const rows: any[] = []
      while (stmt.step()) {
        rows.push(stmt.get())
      }
      return rows
    } finally {
      stmt.free()
    }
  }

  private getAnnotationFields(database: Database, datasetId: string, kind: AnnotationKind) {
    if (!this.traitsOf(database).hasEvalAnnotations) return []
    const rows = this._getRowsByQueryAndParams(
      database,
      'SELECT DISTINCT name, value_type FROM eval_annotations WHERE annotation_kind = ? AND dataset_id = ?',
      [kind, datasetId],
    )
    return rows.map((row) => {
      const [name, value_type] = row
      const stringType = this.parseValue(value_type, 'string')
      return {
        name: this.parseValue(name, 'string'),
        type:
          ANNOTATION_VALUE_TYPE_MAP[stringType as keyof typeof ANNOTATION_VALUE_TYPE_MAP] ||
          'unknown',
      }
    })
  }

  private getSpanAnnotationFields(database: Database, kind: AnnotationKind) {
    if (!this.traitsOf(database).hasSpanAnnotations) return []
    const rows = this._getRowsByQueryAndParams(
      database,
      'SELECT DISTINCT name, value_type FROM span_annotations WHERE annotation_kind = ?',
      [kind],
    )
    return rows.map((row) => {
      const [name, value_type] = row
      const stringType = this.parseValue(value_type, 'string')
      return {
        name: this.parseValue(name, 'string'),
        type:
          ANNOTATION_VALUE_TYPE_MAP[stringType as keyof typeof ANNOTATION_VALUE_TYPE_MAP] ||
          'unknown',
      }
    })
  }
}
