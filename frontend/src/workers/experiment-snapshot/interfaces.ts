import type {
  ExperimentSnapshotDatabaseProvider,
  ExperimentSnapshotModelSource,
  SnapshotCallContext,
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

export interface CallMessage {
  payload: CallPayload
  /** When the caller, or else the proxy, stops waiting for the answer (epoch ms). */
  deadline?: number
  context?: Omit<SnapshotCallContext, 'deadline'>
}
