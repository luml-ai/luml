import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotWorkerProxy } from '@luml/experiments'

const database = vi.hoisted(() => ({ init: vi.fn(), getUniqueDatasetsIds: vi.fn() }))

vi.mock('@luml/experiments', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@luml/experiments')>()),
  ExperimentSnapshotDatabaseProvider: class {
    init = database.init
    getUniqueDatasetsIds = database.getUniqueDatasetsIds
  },
}))

describe('experiment snapshot worker protocol', () => {
  let worker: EventTarget
  let posted: unknown[]
  let scope: {
    onmessage: ((event: MessageEvent) => Promise<void>) | null
    postMessage(data: unknown): void
  }

  function send(data: unknown) {
    return scope.onmessage!(new MessageEvent('message', { data }))
  }

  beforeEach(async () => {
    worker = new EventTarget()
    posted = []
    scope = {
      onmessage: null,
      postMessage(data: unknown) {
        posted.push(data)
        worker.dispatchEvent(new MessageEvent('message', { data }))
      },
    }
    vi.stubGlobal('self', scope)
    vi.resetModules()
    await import('../index')
  })

  afterEach(() => vi.unstubAllGlobals())

  it('initializes the real worker module through the proxy before making provider calls', async () => {
    const postMessage = vi.fn((data: unknown) => void send(data))
    const proxy = new ExperimentSnapshotWorkerProxy(
      Object.assign(worker, { postMessage }) as unknown as Worker,
    )
    const payload = [{ modelId: 'm1', buffer: new ArrayBuffer(8) }]
    database.getUniqueDatasetsIds.mockResolvedValue(['dataset'])

    await proxy.init(payload)

    expect(database.init).toHaveBeenCalledWith({ modelsInfo: payload, wasmUrl: '/sql-wasm.wasm' })
    await expect(proxy.getUniqueDatasetsIds()).resolves.toEqual(['dataset'])
  })

  it('does not answer a call cancelled while it is running', async () => {
    await send({ type: 'init', requestId: 'init', payload: [] })
    let release!: (value: string[]) => void
    database.getUniqueDatasetsIds.mockReturnValue(new Promise((resolve) => (release = resolve)))

    const call = send({
      type: 'call',
      requestId: 'call',
      payload: { method: 'getUniqueDatasetsIds' },
    })
    await send({ type: 'cancel', requestId: 'call' })
    release(['dataset'])
    await call

    expect(posted).toEqual([{ type: 'result', requestId: 'init', data: true }])
  })

  it('answers every call that was not cancelled', async () => {
    await send({ type: 'init', requestId: 'init', payload: [] })
    database.getUniqueDatasetsIds.mockResolvedValue(['dataset'])

    await send({ type: 'call', requestId: 'first', payload: { method: 'getUniqueDatasetsIds' } })
    await send({ type: 'call', requestId: 'second', payload: { method: 'getUniqueDatasetsIds' } })

    expect(posted.slice(1)).toEqual([
      { type: 'result', requestId: 'first', data: ['dataset'] },
      { type: 'result', requestId: 'second', data: ['dataset'] },
    ])
  })
})
