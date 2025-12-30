/// <reference lib="webworker" />

import type { CallPayload, InitPayloadItem } from './interfaces'
import { ExperimentSnapshotDatabaseProvider } from '@/modules/experiment-snapshot/providers/ExperimentSnapshotDatabaseProvider'

let provider: ExperimentSnapshotDatabaseProvider | null = null

const activeRequests = new Set<string>()

async function init(payload: InitPayloadItem[], requestId: string) {
  provider = new ExperimentSnapshotDatabaseProvider()
  await provider.init(payload)
  self.postMessage({ type: 'result', requestId, data: true })
}

async function call(payload: CallPayload, requestId: string) {
  const { method, args } = payload
  if (!provider) {
    throw new Error('Provider not initialized')
  }
  const fn = (provider as any)[method]
  if (typeof fn !== 'function') {
    throw new Error(`Provider method "${method}" does not exist`)
  }
  const result = await fn.apply(provider, args ?? [])
  if (!activeRequests.has(requestId)) return
  self.postMessage({ type: 'result', requestId, data: result })
}

self.onmessage = async (event) => {
  const { type, payload, requestId } = event.data
  activeRequests.add(requestId)
  try {
    switch (type) {
      case 'init':
        await init(payload, requestId)
        break
      case 'call':
        await call(payload, requestId)
        break
      case 'cancel':
        activeRequests.delete(requestId)
        break
    }
  } catch (err: any) {
    activeRequests.delete(requestId)
    self.postMessage({
      type: 'error',
      requestId,
      error: err.message,
    })
  }
}
