import type { Database, SqlJsStatic, SqlValue } from 'sql.js'
import type {
  EvalsColumns,
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  GetEvalsByDatasetParams,
  ModelScores,
  ModelSnapshot,
  ScoreInfo,
  SpansListType,
  SpansParams,
  TraceSpan,
} from '../interfaces/interfaces'
import { safeParse } from '../helpers/helpers'
import { loadAsync as loadZipAsync } from 'jszip'
import initSqlJs from 'sql.js'

interface ModelInfo {
  modelId: string
  buffer: ArrayBuffer
}

export class ExperimentSnapshotDatabaseProvider implements ExperimentSnapshotProvider {
  private _modelsSnapshots: ModelSnapshot[] | null = null
  private evalsDatasetsRequestParams: Record<string, number> = {}

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
    return this.modelsSnapshots
      .map((snapshot) => {
        const database = snapshot.database
        const page = this.evalsDatasetsRequestParams[params.dataset_id] || 1
        this.evalsDatasetsRequestParams[params.dataset_id] = page + 1
        const evals = this.getDatabaseEvalsByDatasetId(database, {
          ...params,
          page,
          modelId: snapshot.modelId,
        })
        return evals
      })
      .flat()
  }

  async resetEvalsDatasetsRequestParams() {
    this.evalsDatasetsRequestParams = {}
  }

  async resetDatasetPage(datasetId: string) {
    delete this.evalsDatasetsRequestParams[datasetId]
  }

  async getTraceSpans(modelId: string, traceId: string) {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === modelId)?.database
    if (!db) return []
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
      const parsedRow = {
        ...row,
        attributes: safeParse(row.attributes as SqlValue),
        events: safeParse(row.events as SqlValue),
        links: safeParse(row.links as SqlValue),
      }
      rows.push(parsedRow)
    }
    stmt.free()
    return rows as unknown as SpansListType
  }

  async getUniqueTraceIds(modelId: string) {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === modelId)?.database
    if (!db) return []
    const queryResult = db.exec('SELECT DISTINCT trace_id FROM spans')
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  async getTraceId(args: SpansParams) {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === args.modelId)?.database
    if (!db) return null
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

  sortSpans(tree: TraceSpan[]): TraceSpan[] {
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

  async getEvalsColumns(datasetId: string): Promise<EvalsColumns> {
    const result = this.modelsSnapshots.reduce(
      (acc, snapshot) => {
        const inputs = this.extractColumnsNames(snapshot.database, 'inputs', datasetId)
        const outputs = this.extractColumnsNames(snapshot.database, 'outputs', datasetId)
        const refs = this.extractColumnsNames(snapshot.database, 'refs', datasetId)
        const scores = this.extractColumnsNames(snapshot.database, 'scores', datasetId)
        const metadata = this.extractColumnsNames(snapshot.database, 'metadata', datasetId)
        inputs.forEach((input) => acc.inputs.add(input))
        outputs.forEach((output) => acc.outputs.add(output))
        refs.forEach((ref) => acc.refs.add(ref))
        scores.forEach((score) => acc.scores.add(score))
        metadata.forEach((meta) => acc.metadata.add(meta))
        return acc
      },
      {
        inputs: new Set<string>(),
        outputs: new Set<string>(),
        refs: new Set<string>(),
        scores: new Set<string>(),
        metadata: new Set<string>(),
      },
    )
    return {
      inputs: Array.from(result.inputs),
      outputs: Array.from(result.outputs),
      refs: Array.from(result.refs),
      scores: Array.from(result.scores),
      metadata: Array.from(result.metadata),
    }
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
            if (typeof scoreValue === 'number') {
              if (!acc[key]) {
                acc[key] = {
                  sum: 0,
                  count: 0,
                }
              }
              acc[key].sum += scoreValue
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
    return [
      {
          "id": "035bb74a-7836-42df-91b4-d5a59497c49a",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": true,
          "user": "Limanskiy",
          "created_at": "2026-03-10T20:56:04",
          "rationale": "simpleee"
      },
      {
          "id": "07f07c6e-67ef-4daf-bb3a-8bcbe7eac13a",
          "name": "exp",
          "annotation_kind": "expectation",
          "value_type": "bool",
          "value": false,
          "user": "Limanskiy",
          "created_at": "2026-03-10T21:14:56",
          "rationale": "123"
      },
      {
          "id": "e1332ead-57b7-48f5-bc52-259b993ebd7a",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": true,
          "user": "Limanskiy",
          "created_at": "2026-03-10T21:56:40",
          "rationale": "1"
      },
      {
          "id": "64fc15e0-0545-4c89-8919-8574878dbd18",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": true,
          "user": "Limanskiy",
          "created_at": "2026-03-10T21:56:49",
          "rationale": "2"
      },
      {
          "id": "5b1d5e52-4df8-4531-9f54-f9a990afb015",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": false,
          "user": "Limanskiy",
          "created_at": "2026-03-10T21:56:55",
          "rationale": "1"
      },
      {
          "id": "4b83d09c-3be6-42fe-8a22-7034a781ccd4",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": false,
          "user": "Limanskiy",
          "created_at": "2026-03-10T21:57:02",
          "rationale": "2"
      },
      {
          "id": "7c27ac90-ff4b-4f1f-bcd6-2912f30e12c3",
          "name": "First",
          "annotation_kind": "feedback",
          "value_type": "bool",
          "value": true,
          "user": "Limanskiy",
          "created_at": "2026-03-10T22:16:10",
          "rationale": "1"
      },
      {
          "id": "bbf0a908-44d7-4f0f-a068-458dad60bcc0",
          "name": "Simple",
          "annotation_kind": "expectation",
          "value_type": "string",
          "value": "String",
          "user": "Limanskiy",
          "created_at": "2026-03-11T07:35:43",
          "rationale": "Rationale"
      }
  ] as any
    return []
  }

  async getEvalsDatasetAnnotationsSummary(datasetId: string) {
    return {
      feedback: [],
      expectations: [],
    }
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
      limit = 20,
      sort_by = 'created_at',
      order = 'desc',
      dataset_id,
      search = '',
      page = 1,
      modelId,
    }: {
      page: number
      modelId: string
    } & GetEvalsByDatasetParams,
  ) {
    const parentColumnsSort = ['created_at', 'id']
    const sortBy = parentColumnsSort.includes(sort_by)
      ? sort_by
      : `COALESCE(json_extract(scores, '$.${sort_by}'), 0)`
    const safeOrder = order?.toLowerCase() === 'asc' ? 'ASC' : 'DESC'
    const offset = (page - 1) * limit
    const searchCondition = search ? `AND id LIKE '%${search}%'` : ''
    const queryResult = database.exec(
      `
      SELECT id, dataset_id, inputs, outputs, refs, scores, metadata
      FROM evals
      WHERE dataset_id = '${dataset_id}'
      ${searchCondition}
      ORDER BY ${sortBy} ${safeOrder}
      LIMIT ${limit}
      OFFSET ${offset}
      `,
    )
    const rows = queryResult[0]?.values || []
    return rows.map((row) => {
      const [id, dataset_id, inputs, outputs, refs, scores, metadata] = row
      return this.prepareEvalData({
        id,
        dataset_id,
        inputs,
        outputs,
        refs,
        scores,
        metadata,
        modelId,
      })
    })
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
  }: Record<string, SqlValue | undefined>) {
    return {
      id: safeParse(id) || '',
      dataset_id: safeParse(dataset_id) || '',
      inputs: safeParse(inputs) || {},
      outputs: safeParse(outputs) || {},
      refs: safeParse(refs) || {},
      scores: safeParse(scores) || {},
      metadata: safeParse(metadata) || {},
      modelId: safeParse(modelId) || '',
    }
  }

  private extractColumnsNames(
    database: Database,
    column: 'inputs' | 'outputs' | 'refs' | 'scores' | 'metadata',
    datasetId: string,
  ) {
    const queryResult = database.exec(
      `SELECT DISTINCT je.key FROM evals, json_each(evals.${column}) AS je WHERE evals.${column} IS NOT NULL AND evals.dataset_id = '${datasetId}' ORDER BY je.key`,
    )
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
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
}
