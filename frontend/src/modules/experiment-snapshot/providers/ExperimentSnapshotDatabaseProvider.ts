import type { Database, QueryExecResult, SqlJsStatic, SqlValue } from 'sql.js'
import type {
  EvalsDatasets,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelSnapshot,
  SpansParams,
  TraceSpan,
} from '../interfaces/interfaces'
import { safeParse } from '../helpers/helpers'
import { loadAsync as loadZipAsync } from 'jszip'
import initSqlJs from 'sql.js'
import sqlWasmUrl from 'sql.js/dist/sql-wasm.wasm?url'

interface ModelInfo {
  modelId: string
  buffer: ArrayBuffer
}

export class ExperimentSnapshotDatabaseProvider implements ExperimentSnapshotProvider {
  private _modelsSnapshots: ModelSnapshot[] | null = null

  private get modelsSnapshots() {
    if (!this._modelsSnapshots) throw new Error('Models snapshots not initialized')
    return this._modelsSnapshots
  }

  async init(data: ModelInfo[]) {
    const SQL = await initSqlJs({ locateFile: () => sqlWasmUrl })
    const snapshotsPromises = data.map(async ({ modelId, buffer }) => {
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

  private getModelMetricsNames(database: Database) {
    const queryResult = database.exec('SELECT key FROM dynamic_metrics')
    const rows = queryResult[0]?.values || []
    return rows.map((row) => this.parseValue(row[0], 'string'))
  }

  async getDynamicMetricData(metricName: string) {
    const data = this.modelsSnapshots.map((snapshot) =>
      this.getModelDynamicMetricData(snapshot.database, metricName, snapshot.modelId),
    )
    return data
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
      const value = row[0]
      const step = row[1]
      if (typeof step !== 'number' || typeof value !== 'number') continue
      data.x.push(step)
      data.y.push(value)
    }
    return data
  }

  async createDatabaseFromBuffer(buffer: ArrayBuffer, SQL: SqlJsStatic) {
    const zip = await loadZipAsync(buffer)
    const dbFile = zip.file('exp.db')
    if (!dbFile) throw new Error('exp.db not found')
    const content = await dbFile.async('uint8array')
    return new SQL.Database(content)
  }

  async getStaticParamsList() {
    const list = this.modelsSnapshots
      .map((snapshot) => this.getStaticParams(snapshot.database, snapshot.modelId))
      .flat()
    return list
  }

  async getEvalsList() {
    const data = this.modelsSnapshots.map((snapshot) =>
      this.getEvals(snapshot.database, snapshot.modelId),
    )
    const notEmptyData = data.filter((modelDatasets) => Object.keys(modelDatasets).length)
    if (!notEmptyData.length) return null
    return notEmptyData.reduce((acc: EvalsDatasets, modelDatasets) => {
      const entries = Object.entries(modelDatasets)
      entries.map(([datasetId, list]) => {
        const existedDataset = acc[datasetId]
        if (existedDataset) {
          existedDataset.push(...list)
        } else {
          acc[datasetId] = list
        }
      })
      return acc
    })
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
    const obj = Object.fromEntries(rows.map((row) => [row[0], this.parseValue(row[1], row[2])]))
    return { ...obj, modelId }
  }

  private getEvals(database: Database, modelId: string): EvalsDatasets {
    const queryResult = database.exec(
      'SELECT id, dataset_id, inputs, outputs, refs, scores, metadata FROM evals LIMIT 100',
    )
    const rows = queryResult[0]?.values || []
    const data: EvalsDatasets = {}
    rows.map((row) => {
      const [id, dsid, inputs, outputs, refs, scores, metadata] = row
      if (typeof dsid !== 'string') throw new Error('Invalid dataset ID')
      if (typeof id !== 'string') throw new Error('Invalid eval ID')
      const existedDataset = data[dsid]
      const info = {
        id,
        dataset_id: dsid,
        inputs: safeParse(inputs) || {},
        outputs: safeParse(outputs) || {},
        refs: safeParse(refs) || {},
        scores: safeParse(scores) || {},
        metadata: safeParse(metadata) || {},
        modelId,
      }
      if (existedDataset) {
        existedDataset.push(info)
      } else {
        data[dsid] = [info]
      }
    })
    return data
  }

  async getTraceSpans(modelId: string, traceId: string) {
    const db = this.modelsSnapshots.find((snapshot) => snapshot.modelId === modelId)?.database
    if (!db) return []
    const results = db.exec(
      `SELECT trace_id, span_id, parent_span_id, name, kind, start_time_unix_nano, end_time_unix_nano, status_code, status_message, attributes, events, links, dfs_span_type FROM spans WHERE trace_id = '${traceId}'`,
    )
    if (!results[0]) return []
    return this.prepareSpansResult(results[0])
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
    if (bridge.length && bridge[0].values.length) {
      return bridge[0].values[0][0]
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

  private prepareSpansResult(result: QueryExecResult) {
    const columns = result.columns
    const values = result.values
    return values.map((array) =>
      array.reduce((acc: any, value, index) => {
        const columnName = columns[index]
        acc[columnName] = safeParse(value)
        return acc
      }, {}),
    )
  }
}
