import type { Database, SqlJsStatic, SqlValue } from 'sql.js'
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
import initSqlJs from 'sql.js'
import type { Trace } from './ExperimentSnapshotApiProvider.interface'
import {
  type Annotation,
  AnnotationKind,
  type AnnotationSummary,
  AnnotationValueType,
} from '@/components/annotations/annotations.interface'
import { SearchEvalsUtils, SearchTracesUtils } from '@/utils/_search_utils'

interface ModelInfo {
  modelId: string
  buffer: ArrayBuffer
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
  private tracesRequestParams: Record<string, number> = {}

  private get modelsSnapshots() {
    if (!this._modelsSnapshots) throw new Error('Models snapshots not initialized')
    return this._modelsSnapshots
  }

  async init(data: { modelsInfo: ModelInfo[]; wasmUrl: string }) {
    const SQL = await initSqlJs({ locateFile: () => data.wasmUrl })
    const snapshotsPromises = data.modelsInfo.map(async ({ modelId, buffer }) => {
      const database = await this.createDatabaseFromBuffer(buffer, SQL)
      return { modelId, database }
    })
    this._modelsSnapshots = await Promise.all(snapshotsPromises)
  }

  async getDynamicMetricsNames() {
    const names = this.modelsSnapshots.map((snapshot) =>
      this.getModelMetricsNames(snapshot.database),
    )
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
    const promises = this.modelsSnapshots.map(async (snapshot) => {
      const page = this.evalsDatasetsRequestParams[params.dataset_id] || 1
      this.evalsDatasetsRequestParams[params.dataset_id] = page + 1
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
    const promises = this.modelsSnapshots.map(async (snapshot) => {
      const page = this.evalsDatasetsRequestParams[params.dataset_id] || 1
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

  async resetEvalsDatasetsRequestParams() {
    this.evalsDatasetsRequestParams = {}
  }

  async resetDatasetPage(datasetId: string) {
    delete this.evalsDatasetsRequestParams[datasetId]
  }

  async getTraceSpans(modelId: string, traceId: string) {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === modelId)?.database
    if (!db) throw new Error('Database not found')
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
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === args.modelId)?.database
    if (!db) throw new Error('Database not found')
    const bridge = db.exec(
      `SELECT trace_id FROM eval_traces_bridge WHERE eval_dataset_id = '${args.datasetId}' AND eval_id = '${args.evalId}' LIMIT 1`,
    )
    if (bridge[0]?.values.length) {
      return bridge[0].values[0]?.[0] ?? null
    }
    return null
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

  async getDatasetAverageScores(datasetId: string): Promise<ModelScores[]> {
    return this.modelsSnapshots.map((snapshot) => {
      const queryResult = snapshot.database.exec(
        `SELECT scores FROM evals WHERE scores IS NOT NULL AND dataset_id = '${datasetId}'`,
      )
      const rows = queryResult[0]?.values || []
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
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === artifactId)?.database
    if (!db) throw new Error('Database not found')
    const hasAnnotations = this.isDatabaseHasAnnotations(db)
    if (!hasAnnotations) return []
    const queryResult = db.exec(
      `
      SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
      FROM eval_annotations
      WHERE eval_id = '${evalId}' AND dataset_id = '${datasetId}'
      `,
    )
    const rows = queryResult[0]?.values || []
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
    const queryResult = db.exec(
      `SELECT id, dataset_id, inputs, outputs, refs, scores, metadata FROM evals WHERE id = '${evalId}'`,
    )
    const row = queryResult[0]?.values[0]
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
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === artifactId)?.database
    if (!db) throw new Error('Database not found')
    const hasAnnotations = this.isDatabaseHasAnnotations(db)
    if (!hasAnnotations) return []
    const queryResult = db.exec(
      `SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale FROM span_annotations WHERE trace_id = '${traceId}' AND span_id = '${spanId}'`,
    )
    const rows = queryResult[0]?.values || []
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
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === artifactId)?.database
    if (!db) throw new Error('Database not found')
    const hasAnnotations = this.isDatabaseHasAnnotations(db)
    if (!hasAnnotations) return { feedback: [], expectations: [] }
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
    const database = this.modelsSnapshots.find(
      (snapshot) => snapshot.modelId === artifactId,
    )?.database
    if (!database) throw new Error('Database not found')
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
    const offset = params.page && params.limit ? (params.page - 1) * params.limit : 0
    const limitQuery = params.limit ? `LIMIT ${params.limit}` : ''
    const offsetQuery = offset ? `OFFSET ${offset}` : ''

    const whereParts: string[] = []
    const whereParams: SqlValue[] = []
    if (params.search) {
      whereParts.push(`trace_id LIKE ?`)
      whereParams.push(`%${params.search}%`)
    }
    for (const filter of params.filters || []) {
      const [where, filterParams] = SearchTracesUtils.toSql(filter)
      if (where) {
        whereParts.push(where)
        whereParams.push(...(filterParams as SqlValue[]))
      }
    }

    const whereCondition = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''

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
      ORDER BY ${params.sort_by} ${params.order}
      ${limitQuery}
      ${offsetQuery}
    `
    const rows = this._getRowsByQueryAndParams(database, query, whereParams)
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
    const queryResult = database.exec(
      `
      SELECT eval_id
      FROM eval_traces_bridge
      WHERE trace_id = '${traceId}'
      `,
    )
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private getModelDynamicMetricData(database: Database, metricName: string, modelId: string) {
    const queryResult = database.exec(
      `SELECT value, step FROM dynamic_metrics WHERE key = '${metricName}'`,
    )
    const rows = queryResult[0]?.values || []
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
    const parentColumnsSort = ['created_at', 'id']
    const sortBy = parentColumnsSort.includes(sort_by)
      ? sort_by
      : `COALESCE(json_extract(scores, '$.${sort_by}'), 0)`
    const safeOrder = order?.toLowerCase() === 'asc' ? 'ASC' : 'DESC'
    const limitQuery = limit ? `LIMIT ${limit}` : ''
    const offset = page && limit ? (page - 1) * limit : 0
    const offsetQuery = offset ? `OFFSET ${offset}` : ''

    const whereParts: string[] = []
    const params: SqlValue[] = []

    whereParts.push(`dataset_id = ?`)
    params.push(dataset_id)

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
      const [where, filterParams] = SearchEvalsUtils.toSql(filter)

      if (where) {
        whereParts.push(where)
        params.push(...(filterParams as SqlValue[]))
      }
    }

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
      id: safeParse(id) || '',
      dataset_id: safeParse(dataset_id) || '',
      inputs: safeParse(inputs) || {},
      outputs: safeParse(outputs) || {},
      refs: safeParse(refs) || {},
      scores: safeParse(scores) || {},
      metadata: safeParse(metadata) || {},
      modelId: safeParse(modelId) || '',
      annotations,
    }
  }

  private extractEvalColumns(
    database: Database,
    column: 'inputs' | 'outputs' | 'refs' | 'scores' | 'metadata',
    datasetId: string,
  ) {
    const queryResult = database.exec(
      `
      SELECT je.key, je.type
      FROM evals, json_each(evals.${column}) AS je
      WHERE evals.${column} IS NOT NULL AND evals.dataset_id = '${datasetId}'
      GROUP BY je.key
      ORDER BY je.key
      `,
    )
    const rows = queryResult[0]?.values || []
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
    const queryResult = database.exec('SELECT DISTINCT dataset_id FROM evals')
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private parseValue(val: any, type: SqlValue | 'json' | 'int' | 'float' | 'bool') {
    if (type === 'json') return JSON.parse(val)
    if (type === 'int') return parseInt(val)
    if (type === 'float') return parseFloat(val)
    if (type === 'bool') return val === 'true'
    return val
  }

  private getStaticParams(database: Database, modelId: string): ExperimentSnapshotStaticParams[] {
    const queryResult = database.exec('SELECT key, value, value_type FROM static_params')
    const rows = queryResult[0]?.values || []
    const obj = Object.fromEntries(
      rows.map((row) => [row[0], this.parseValue(row[1], row[2] as SqlValue)]),
    )
    return { ...obj, modelId }
  }

  private getModelMetricsNames(database: Database) {
    const queryResult = database.exec('SELECT key FROM dynamic_metrics')
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private async createDatabaseFromBuffer(buffer: ArrayBuffer, SQL: SqlJsStatic) {
    const zip = await loadZipAsync(buffer)
    const dbFile = zip.file('exp.db')
    if (!dbFile) throw new Error('exp.db not found')
    const content = await dbFile.async('uint8array')
    return new SQL.Database(content)
  }

  private isDatabaseHasAnnotations(database: Database) {
    const version = database.exec('PRAGMA user_version')[0]?.values[0]
    if (!version) return false
    const versionNumber = this.parseValue(version, 'int')
    return versionNumber >= 1
  }

  private getTraceAnnotations(database: Database, traceId: string) {
    const hasAnnotations = this.isDatabaseHasAnnotations(database)
    if (!hasAnnotations) return { feedback: [], expectations: [] }
    const queryResult = database.exec(
      `
      SELECT name, value, annotation_kind, value_type
      FROM span_annotations
      WHERE trace_id = '${traceId}'
      ORDER BY name
    `,
    )
    const rows = queryResult[0]?.values || []
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
      value: value as number | boolean | string,
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
    const queryResult = database.exec(`SELECT id FROM evals WHERE dataset_id = '${datasetId}'`)
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  private async getFlatPromisesResponse<T>(promises: Promise<T[]>[]): Promise<T[]> {
    const results = await Promise.all(promises)
    return results.flat()
  }

  private getSnapAnnotationsCountByDatabase(database: Database, spanId: string): number {
    const hasAnnotations = this.isDatabaseHasAnnotations(database)
    if (!hasAnnotations) return 0
    const queryResult = database.exec(
      `SELECT COUNT(*) FROM span_annotations WHERE span_id = '${spanId}'`,
    )
    const count = queryResult[0]?.values[0]?.[0]
    return this.parseValue(count, 'int')
  }

  private getSqliteType(type: string): (typeof SQLLITE_TYPE_MAP)[keyof typeof SQLLITE_TYPE_MAP] {
    return SQLLITE_TYPE_MAP[type as keyof typeof SQLLITE_TYPE_MAP] || 'unknown'
  }

  private _getRowsByQueryAndParams(database: Database, query: string, params: SqlValue[]): any[] {
    const stmt = database.prepare(query)
    stmt.bind(params)
    const rows: any[] = []
    while (stmt.step()) {
      rows.push(Object.values(stmt.getAsObject()))
    }
    stmt.free()
    return rows
  }

  private getAnnotationFields(database: Database, datasetId: string, kind: AnnotationKind) {
    const hasAnnotations = this.isDatabaseHasAnnotations(database)
    if (!hasAnnotations) return []
    const queryResult = database.exec(
      `SELECT DISTINCT name, value_type FROM eval_annotations WHERE annotation_kind = '${kind}' AND dataset_id = '${datasetId}'`,
    )
    const rows = queryResult[0]?.values || []
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
    const hasAnnotations = this.isDatabaseHasAnnotations(database)
    if (!hasAnnotations) return []
    const queryResult = database.exec(`SELECT DISTINCT name, value_type FROM span_annotations WHERE annotation_kind = '${kind}'`)
    const rows = queryResult[0]?.values || []
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
