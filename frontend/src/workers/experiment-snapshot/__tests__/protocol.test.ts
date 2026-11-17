import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ExperimentSnapshotWorkerProxy,
  SNAPSHOT_SOURCE_EXPIRED,
  SnapshotSourceExpiredError,
} from '@luml/experiments'

const database = vi.hoisted(() => ({
  init: vi.fn(),
  reopenSnapshot: vi.fn(),
  getUniqueDatasetsIds: vi.fn(),
}))

vi.mock('@luml/experiments', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@luml/experiments')>()),
  ExperimentSnapshotDatabaseProvider: class {
    init = database.init
    reopenSnapshot = database.reopenSnapshot
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
    database.init.mockReset()
    database.init.mockResolvedValue([])
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

    expect(database.init).toHaveBeenCalledWith(
      { modelsInfo: payload, sqliteWasmUrl: expect.stringMatching(/sqlite3.*\.wasm$/) },
      expect.any(AbortSignal),
    )
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

    expect(posted).toEqual([{ type: 'result', requestId: 'init', data: [] }])
  })

  it('aborts the downloads of a cancelled init and posts no answer for it', async () => {
    let signal: AbortSignal | undefined
    let release!: () => void
    database.init.mockImplementation((_data: unknown, given: AbortSignal) => {
      signal = given
      return new Promise<never[]>((resolve) => (release = () => resolve([])))
    })

    const initialized = send({ type: 'init', requestId: 'init', payload: [] })
    await send({ type: 'cancel', requestId: 'init' })
    expect(signal?.aborted).toBe(true)
    release()
    await initialized

    expect(posted).toEqual([])
  })

  it('reopens one snapshot with its renewed source and an abort signal', async () => {
    await send({ type: 'init', requestId: 'init', payload: [] })
    database.reopenSnapshot.mockResolvedValue([])
    const source = { url: 'https://bucket/a?sig=2' }

    await send({ type: 'reopen', requestId: 'reopen', payload: { modelId: 'm1', source } })

    expect(database.reopenSnapshot).toHaveBeenCalledWith('m1', source, expect.any(AbortSignal))
    expect(posted.at(-1)).toEqual({ type: 'result', requestId: 'reopen', data: [] })
  })

  it('posts error messages without URLs or credentials', async () => {
    await send({ type: 'init', requestId: 'init', payload: [] })
    database.getUniqueDatasetsIds.mockRejectedValue(
      new DOMException("Failed to load 'https://bucket/a?X-Amz-Signature=SECRET'.", 'NetworkError'),
    )

    await send({ type: 'call', requestId: 'call', payload: { method: 'getUniqueDatasetsIds' } })

    expect(posted.at(-1)).toEqual({
      type: 'error',
      requestId: 'call',
      error: "Failed to load 'https://bucket'.",
    })
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

  it('marks an expired snapshot source in the error so the proxy can renew its URL', async () => {
    await send({ type: 'init', requestId: 'init', payload: [] })
    database.getUniqueDatasetsIds.mockRejectedValue(
      new SnapshotSourceExpiredError('m1', 'Range request returned status 403'),
    )

    await send({ type: 'call', requestId: 'call', payload: { method: 'getUniqueDatasetsIds' } })

    expect(posted.at(-1)).toEqual({
      type: 'error',
      requestId: 'call',
      error: 'Range request returned status 403',
      code: SNAPSHOT_SOURCE_EXPIRED,
      modelId: 'm1',
    })
  })
})
