/// <reference lib="webworker" />

import type { CallPayload, InitPayloadItem, ReopenPayload } from './interfaces'
import {
  ExperimentSnapshotDatabaseProvider,
  redactSecrets,
  snapshotErrorFields,
} from '@luml/experiments'
import sqliteWasmUrl from '@sqlite.org/sqlite-wasm/sqlite3.wasm?url'

let provider: ExperimentSnapshotDatabaseProvider | null = null

const activeRequests = new Map<string, AbortController>()

function post(requestId: string, data: unknown) {
  if (!activeRequests.has(requestId)) return
  self.postMessage({ type: 'result', requestId, data })
}

async function init(payload: InitPayloadItem[], requestId: string, signal: AbortSignal) {
  provider = new ExperimentSnapshotDatabaseProvider()
  const failures = await provider.init({ modelsInfo: payload, sqliteWasmUrl }, signal)
  post(requestId, failures)
}

async function reopen(payload: ReopenPayload, requestId: string, signal: AbortSignal) {
  if (!provider) throw new Error('Provider not initialized')
  post(requestId, await provider.reopenSnapshot(payload.modelId, payload.source, signal))
}

async function call(payload: CallPayload, requestId: string) {
  const { method, args } = payload
  if (!provider) {
    throw new Error('Provider not initialized')
  }
  const fn = provider[method] as (...args: unknown[]) => unknown
  if (typeof fn !== 'function') {
    throw new Error(`Provider method "${method}" does not exist`)
  }
  const result = await fn.apply(provider, args ?? [])
  post(requestId, result)
}

self.onmessage = async (event) => {
  const { type, payload, requestId } = event.data
  if (type === 'cancel') {
    // Stops downloads of an abandoned init or reopen; the answer is not posted.
    activeRequests.get(requestId)?.abort()
    activeRequests.delete(requestId)
    return
  }
  const controller = new AbortController()
  activeRequests.set(requestId, controller)
  try {
    switch (type) {
      case 'init':
        await init(payload, requestId, controller.signal)
        break
      case 'reopen':
        await reopen(payload, requestId, controller.signal)
        break
      case 'call':
        await call(payload, requestId)
        break
    }
  } catch (err: unknown) {
    const { message } = (err ?? {}) as { message?: unknown }
    self.postMessage({
      type: 'error',
      requestId,
      error: redactSecrets(typeof message === 'string' ? message : String(err)),
      ...snapshotErrorFields(err),
    })
  } finally {
    activeRequests.delete(requestId)
  }
}
