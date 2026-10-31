import { afterEach, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotWorkerProxy } from '../ExperimentSnapshotWorkerProxy'

const database = vi.hoisted(() => ({ init: vi.fn(), getUniqueDatasetsIds: vi.fn() }))

vi.mock('@luml/experiments', () => ({
  ExperimentSnapshotDatabaseProvider: class {
    init = database.init
    getUniqueDatasetsIds = database.getUniqueDatasetsIds
  },
}))

describe('experiment snapshot worker protocol', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('initializes the real worker module through the proxy before making provider calls', async () => {
    const worker = new EventTarget()
    const scope = {
      onmessage: null as ((event: MessageEvent) => Promise<void>) | null,
      postMessage(data: unknown) {
        worker.dispatchEvent(new MessageEvent('message', { data }))
      },
    }
    vi.stubGlobal('self', scope)
    vi.resetModules()
    await import('../../../../../../../frontend/src/workers/experiment-snapshot/index')
    const postMessage = vi.fn((data: unknown) => {
      void scope.onmessage!(new MessageEvent('message', { data }))
    })
    const proxy = new ExperimentSnapshotWorkerProxy(
      Object.assign(worker, { postMessage }) as unknown as Worker,
    )
    const payload = [{ modelId: 'm1', buffer: new ArrayBuffer(8) }]
    database.getUniqueDatasetsIds.mockResolvedValue(['dataset'])

    await proxy.init(payload)

    expect(database.init).toHaveBeenCalledWith({ modelsInfo: payload, wasmUrl: '/sql-wasm.wasm' })
    await expect(proxy.getUniqueDatasetsIds()).resolves.toEqual(['dataset'])
  })
})
