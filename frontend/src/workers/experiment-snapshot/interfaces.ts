import type { ExperimentSnapshotDatabaseProvider } from '@luml/experiments'

export interface InitPayloadItem {
  modelId: string
  buffer: ArrayBuffer
}

export interface CallPayload<
  M extends keyof ExperimentSnapshotDatabaseProvider = keyof ExperimentSnapshotDatabaseProvider,
> {
  method: M
  args?: ExperimentSnapshotDatabaseProvider[M] extends (...args: infer A) => any ? A : never[]
}
