import type { Database, SqlValue } from 'sql.js'
import type {
  EvalsDatasets,
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ModelSnapshot,
} from '../interfaces/interfaces'
import { safeParse } from '../helpers/helpers'

export class ExperimentSnapshotDatabaseProvider implements ExperimentSnapshotProvider {
  modelsSnapshots: ModelSnapshot[]

  constructor(snapshots: ModelSnapshot[]) {
    this.modelsSnapshots = snapshots
  }

  async getStaticParamsList() {
    const list = this.modelsSnapshots
      .map((snapshot) => this.getStaticParams(snapshot.database, snapshot.modelId))
      .flat()
    return list
  }

  async getDynamicMetricsList() {
    const list = this.modelsSnapshots.map((snapshot) =>
      this.getDynamicMetrics(snapshot.database, snapshot.modelId),
    )
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

  private getStaticParams(database: Database, modelId: number): ExperimentSnapshotStaticParams[] {
    const queryResult = database.exec('SELECT key, value, value_type FROM static_params')
    const rows = queryResult[0]?.values || []
    const obj = Object.fromEntries(rows.map((row) => [row[0], this.parseValue(row[1], row[2])]))
    return { ...obj, modelId }
  }

  private getDynamicMetrics(database: Database, modelId: number) {
    const queryResult = database.exec(
      'SELECT key, value, step FROM dynamic_metrics ORDER BY key, step',
    )
    const rows = queryResult[0]?.values || []
    const grouped: ExperimentSnapshotDynamicMetrics = {}
    rows.map(([key, value, step]) => {
      if (typeof key !== 'string' && typeof key !== 'number') return
      if (!grouped[key]) grouped[key] = { x: [], y: [], modelId }
      if (typeof step !== 'number' || typeof value !== 'number') return
      grouped[key].x.push(step)
      grouped[key].y.push(value)
    })
    return grouped
  }

  private getEvals(database: Database, modelId: number): EvalsDatasets {
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
}
