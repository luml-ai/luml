import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotWorkerProxy } from '../ExperimentSnapshotWorkerProxy'

class FakeWorker extends EventTarget {
  readonly postMessage = vi.fn()
  readonly addEventListener = vi.fn(super.addEventListener.bind(this))
  readonly removeEventListener = vi.fn(super.removeEventListener.bind(this))

  respond(data: unknown) {
    this.dispatchEvent(new MessageEvent('message', { data }))
  }
}

describe('ExperimentSnapshotWorkerProxy', () => {
  let worker: FakeWorker
  let proxy: ExperimentSnapshotWorkerProxy

  beforeEach(() => {
    vi.useFakeTimers()
    worker = new FakeWorker()
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function expectCleanedUp() {
    for (const type of ['message', 'error', 'messageerror']) {
      const added = worker.addEventListener.mock.calls.filter(([event]) => event === type)
      const removed = worker.removeEventListener.mock.calls.filter(([event]) => event === type)
      expect(added.length).toBeGreaterThan(0)
      expect(removed).toHaveLength(added.length)
      for (const listener of added) expect(removed).toContainEqual(listener)
    }
    expect(vi.getTimerCount()).toBe(0)
  }

  it('initializes with the worker init protocol and resolves its response', async () => {
    const payload = [{ modelId: 'm1', buffer: new ArrayBuffer(8) }]
    const initialized = proxy.init(payload)
    const [message] = worker.postMessage.mock.calls[0]

    expect(message).toEqual({ type: 'init', requestId: expect.any(String), payload })
    worker.respond({ type: 'result', requestId: message.requestId, data: true })

    await initialized
    expectCleanedUp()
  })

  it('matches concurrent responses by request id and ignores unrelated messages', async () => {
    const first = proxy.getUniqueDatasetsIds()
    const second = proxy.getDynamicMetricsNames()
    const [firstMessage, secondMessage] = worker.postMessage.mock.calls.map(([message]) => message)
    expect(firstMessage).toMatchObject({
      type: 'call',
      payload: { method: 'getUniqueDatasetsIds' },
    })
    worker.respond(null)
    worker.respond({ type: 'result', requestId: 'unrelated', data: 'ignored' })
    worker.respond({ type: 'progress', requestId: firstMessage.requestId })
    worker.respond({ type: 'result', requestId: secondMessage.requestId, data: ['loss'] })
    worker.respond({ type: 'result', requestId: firstMessage.requestId, data: ['dataset'] })

    await expect(first).resolves.toEqual(['dataset'])
    await expect(second).resolves.toEqual(['loss'])
    expectCleanedUp()
  })

  it('rejects worker protocol errors and removes abort listeners', async () => {
    const controller = new AbortController()
    const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
    const result = proxy.getUniqueDatasetsIds(controller.signal)
    const [message] = worker.postMessage.mock.calls[0]
    worker.respond({ type: 'error', requestId: message.requestId, error: 'query failed' })

    await expect(result).rejects.toBe('query failed')
    expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function))
    expectCleanedUp()
  })

  it.each(['error', 'messageerror'])('rejects all pending calls on worker %s', async (type) => {
    const first = proxy.getUniqueDatasetsIds()
    const second = proxy.init([])
    worker.dispatchEvent(
      type === 'error'
        ? new ErrorEvent('error', { message: 'worker crashed' })
        : new MessageEvent('messageerror'),
    )

    await expect(first).rejects.toBeInstanceOf(Error)
    await expect(second).rejects.toBeInstanceOf(Error)
    expectCleanedUp()
  })

  it('times out a silent worker, cancels the request and removes listeners', async () => {
    const result = proxy.getUniqueDatasetsIds()
    const rejection = expect(result).rejects.toThrow(/timed out/i)
    const [message] = worker.postMessage.mock.calls[0]
    await vi.advanceTimersByTimeAsync(60_000)

    await rejection
    expect(worker.postMessage).toHaveBeenLastCalledWith({
      type: 'cancel',
      requestId: message.requestId,
    })
    expectCleanedUp()
  })

  it('cleans up when posting the request throws', async () => {
    worker.postMessage.mockImplementation(() => {
      throw new DOMException('cannot clone', 'DataCloneError')
    })

    await expect(proxy.init([])).rejects.toMatchObject({ name: 'DataCloneError' })
    expectCleanedUp()
  })

  it('aborts a pending call even if posting cancellation throws', async () => {
    const controller = new AbortController()
    const result = proxy.getUniqueDatasetsIds(controller.signal)
    worker.postMessage.mockImplementation(() => {
      throw new Error('worker unavailable')
    })
    controller.abort()

    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    expectCleanedUp()
  })

  it('does not send a call for an already aborted signal', async () => {
    const controller = new AbortController()
    controller.abort()

    await expect(proxy.getUniqueDatasetsIds(controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(worker.postMessage.mock.calls.every(([message]) => message.type === 'cancel')).toBe(true)
    expectCleanedUp()
  })

  it('cleans up an init request when the worker never answers', async () => {
    const result = proxy.init([])
    const rejection = expect(result).rejects.toThrow(/timed out/i)
    await vi.advanceTimersByTimeAsync(60_000)

    await rejection
    expectCleanedUp()
  })
})
