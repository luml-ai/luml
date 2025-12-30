import type { ExperimentSnapshotDatabaseProvider } from '@/modules/experiment-snapshot'

export interface InitPayloadItem {
  modelId: string
  buffer: ArrayBuffer
}

export interface CallPayload {
  method: keyof ExperimentSnapshotDatabaseProvider
  args?: any[]
}
