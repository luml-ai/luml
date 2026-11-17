import type {
  ExperimentSnapshotDatabaseProvider,
  ExperimentSnapshotModelSource,
  SnapshotSourceLocation,
} from '@luml/experiments'

export type InitPayloadItem = ExperimentSnapshotModelSource

export interface ReopenPayload {
  modelId: string
  source: SnapshotSourceLocation
}

export interface CallPayload<
  M extends keyof ExperimentSnapshotDatabaseProvider = keyof ExperimentSnapshotDatabaseProvider,
> {
  method: M
  args?: ExperimentSnapshotDatabaseProvider[M] extends (...args: infer A) => unknown ? A : never[]
}
