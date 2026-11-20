import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { ExperimentSnapshotWorkerProxy } from '../ExperimentSnapshotWorkerProxy'
import {
  isSnapshotWorkerTerminated,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourceRedirectError,
  SnapshotSourceTooLargeError,
  SnapshotTooLargeForBrowserError,
} from '../snapshot-source/errors'
import type { SnapshotSourceRef } from '../snapshot-source/sourceLocation'

class FakeWorker extends EventTarget {
  readonly postMessage = vi.fn()
  readonly terminate = vi.fn()
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
    vi.unstubAllGlobals()
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

  it('initializes on an HTTP origin without secure-context crypto APIs', async () => {
    vi.stubGlobal('crypto', {})
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

  it('forwards a span payload request to the worker', async () => {
    const payload = { attributes: '{}', events: null, links: null, status_message: null }
    const result = proxy.getSpanPayload('m1', 't1', 's1')
    const [message] = worker.postMessage.mock.calls[0]

    expect(message).toMatchObject({
      type: 'call',
      payload: { method: 'getSpanPayload', args: ['m1', 't1', 's1'] },
    })
    worker.respond({ type: 'result', requestId: message.requestId, data: payload })

    await expect(result).resolves.toEqual(payload)
    expectCleanedUp()
  })

  it('rejects worker protocol errors and removes abort listeners', async () => {
    const controller = new AbortController()
    const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
    const result = proxy.getUniqueDatasetsIds(controller.signal)
    const [message] = worker.postMessage.mock.calls[0]
    worker.respond({ type: 'error', requestId: message.requestId, error: 'query failed' })

    await expect(result).rejects.toMatchObject({ message: 'query failed' })
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

  it('uses the configured request timeout', async () => {
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, {
      requestTimeoutMs: 1_000,
    })
    const result = proxy.getUniqueDatasetsIds()
    const rejection = expect(result).rejects.toThrow(/timed out/i)
    await vi.advanceTimersByTimeAsync(999)
    expect(vi.getTimerCount()).toBe(1)
    await vi.advanceTimersByTimeAsync(1)

    await rejection
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

  it('aborts a pending init and cancels it in the worker', async () => {
    const controller = new AbortController()
    const result = proxy.init([], controller.signal)
    const [message] = worker.postMessage.mock.calls[0]
    controller.abort()

    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    expect(worker.postMessage).toHaveBeenLastCalledWith({
      type: 'cancel',
      requestId: message.requestId,
    })
    expectCleanedUp()
  })

  it('rejects pending requests at once when terminated', async () => {
    const first = proxy.getUniqueDatasetsIds()
    const second = proxy.init([])
    proxy.terminate()

    for (const result of [first, second]) {
      const error = await result.catch((reason: unknown) => reason)
      expect(error).toMatchObject({
        name: 'ExperimentSnapshotWorkerTerminatedError',
        message: 'Experiment snapshot worker was terminated',
      })
      expect(isSnapshotWorkerTerminated(error)).toBe(true)
    }
    expect(worker.terminate).toHaveBeenCalledOnce()
    expectCleanedUp()
  })

  it('does not report a worker that failed on its own as terminated', async () => {
    const result = proxy.getUniqueDatasetsIds()
    worker.dispatchEvent(new ErrorEvent('error', { message: 'worker crashed' }))

    const error = await result.catch((reason: unknown) => reason)
    expect(error).toMatchObject({ name: 'Error', message: 'worker crashed' })
    expect(isSnapshotWorkerTerminated(error)).toBe(false)
  })

  it('rejects requests made after termination without posting them', async () => {
    proxy.terminate()
    proxy.terminate()

    const error = await proxy.resetTracesRequestParams().catch((reason: unknown) => reason)
    expect(error).toMatchObject({ message: 'Experiment snapshot worker was terminated' })
    expect(isSnapshotWorkerTerminated(error)).toBe(true)
    expect(worker.postMessage).not.toHaveBeenCalled()
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cleans up an init request when the worker never answers', async () => {
    const result = proxy.init([])
    const rejection = expect(result).rejects.toThrow(/timed out/i)
    await vi.advanceTimersByTimeAsync(60_000)

    await rejection
    expectCleanedUp()
  })
})

describe('ExperimentSnapshotWorkerProxy source URL renewal', () => {
  const rangeSource = {
    kind: 'range',
    url: 'https://bucket/a?sig=1',
    offset: 512,
    size: 4096,
  } as const
  const expired = { code: SNAPSHOT_SOURCE_EXPIRED, modelId: 'm1', error: 'Range request failed' }
  type RenewUrl = (id: string, failedUrl: string) => Promise<string>
  let worker: FakeWorker
  let sourceUrls: { get: Mock<(id: string) => Promise<string>>; renew: Mock<RenewUrl> }
  let proxy: ExperimentSnapshotWorkerProxy

  async function nextMessage(index: number) {
    await vi.waitFor(() => expect(worker.postMessage.mock.calls.length).toBeGreaterThan(index))
    return worker.postMessage.mock.calls[index]![0]
  }

  async function initialized() {
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    const message = await nextMessage(0)
    worker.respond({ type: 'result', requestId: message.requestId, data: true })
    await init
  }

  beforeEach(() => {
    worker = new FakeWorker()
    sourceUrls = {
      get: vi.fn(async () => rangeSource.url),
      renew: vi.fn(async () => 'https://bucket/a?sig=2'),
    }
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, { sourceUrls })
  })

  it('renews the URL once and retries the call once after a source failure', async () => {
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    const first = await nextMessage(1)
    worker.respond({ type: 'error', requestId: first.requestId, ...expired })
    const update = await nextMessage(2)
    expect(update.payload).toEqual({
      method: 'setSourceUrl',
      args: ['m1', 'https://bucket/a?sig=2'],
    })
    worker.respond({ type: 'result', requestId: update.requestId, data: undefined })
    const retry = await nextMessage(3)
    expect(retry.payload).toEqual(first.payload)
    worker.respond({ type: 'result', requestId: retry.requestId, data: ['dataset'] })

    await expect(result).resolves.toEqual(['dataset'])
    expect(sourceUrls.renew).toHaveBeenCalledExactlyOnceWith('m1', rangeSource.url)
  })

  it('resends the renewed URL when an abort stopped the hand-over to the worker', async () => {
    await initialized()
    let finishRenewal!: (url: string) => void
    sourceUrls.renew.mockImplementation(() => new Promise((resolve) => (finishRenewal = resolve)))
    const controller = new AbortController()
    const aborted = proxy.getUniqueDatasetsIds(controller.signal)

    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...expired })
    await vi.waitFor(() => expect(sourceUrls.renew).toHaveBeenCalledOnce())
    controller.abort()
    finishRenewal('https://bucket/a?sig=2')
    await expect(aborted).rejects.toThrow()
    const sent = worker.postMessage.mock.calls.map(([message]) => message.payload?.method)
    expect(sent).not.toContain('setSourceUrl')

    sourceUrls.get.mockResolvedValue('https://bucket/a?sig=2')
    const next = proxy.getUniqueDatasetsIds()
    const update = await nextMessage(sent.length)
    expect(update.payload).toEqual({
      method: 'setSourceUrl',
      args: ['m1', 'https://bucket/a?sig=2'],
    })
    worker.respond({ type: 'result', requestId: update.requestId })
    const retry = await nextMessage(sent.length + 1)
    worker.respond({ type: 'result', requestId: retry.requestId, data: ['d'] })
    await expect(next).resolves.toEqual(['d'])
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
  })

  it('surfaces the error when the retried call fails again, without renewing twice', async () => {
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...expired })
    worker.respond({ type: 'result', requestId: (await nextMessage(2)).requestId })
    worker.respond({ type: 'error', requestId: (await nextMessage(3)).requestId, ...expired })

    await expect(result).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(4)
  })

  it('surfaces a 4xx without a retry when the renewal hands back the failed URL', async () => {
    sourceUrls.renew.mockResolvedValue(rangeSource.url)
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    const forbidden = { ...expired, status: 403 }
    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...forbidden })

    await expect(result).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
    await expect(result).rejects.toMatchObject({ status: 403 })
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['a request without an answer', undefined],
    ['a 500', 500],
    ['a 503', 503],
    ['a 429', 429],
  ])(
    'retries once with the same URL after %s when the renewal hands it back',
    async (_label, status) => {
      sourceUrls.renew.mockResolvedValue(rangeSource.url)
      await initialized()
      const result = proxy.getUniqueDatasetsIds()

      const first = await nextMessage(1)
      worker.respond({ type: 'error', requestId: first.requestId, ...expired, status })
      const retry = await nextMessage(2)
      expect(retry.payload).toEqual(first.payload)
      worker.respond({ type: 'result', requestId: retry.requestId, data: ['dataset'] })

      await expect(result).resolves.toEqual(['dataset'])
      expect(sourceUrls.renew).toHaveBeenCalledOnce()
      expect(worker.postMessage).toHaveBeenCalledTimes(3)
    },
  )

  it('surfaces a transient failure that repeats on the retry with the same URL', async () => {
    sourceUrls.renew.mockResolvedValue(rangeSource.url)
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    const failing = { ...expired, status: 500 }
    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...failing })
    worker.respond({ type: 'error', requestId: (await nextMessage(2)).requestId, ...failing })

    await expect(result).rejects.toMatchObject({ code: SNAPSHOT_SOURCE_EXPIRED, status: 500 })
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(3)
  })

  it('renews each model once when their URLs expire together, and the call succeeds', async () => {
    const init = proxy.init([
      { modelId: 'm1', source: rangeSource },
      { modelId: 'm2', source: { ...rangeSource, url: 'https://bucket/b?sig=1' } },
    ])
    worker.respond({ type: 'result', requestId: (await nextMessage(0)).requestId, data: true })
    await init
    sourceUrls.get.mockImplementation(async (id) =>
      id === 'm1' ? rangeSource.url : 'https://bucket/b?sig=1',
    )
    sourceUrls.renew.mockImplementation(async (id) => `https://bucket/${id}?sig=2`)
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...expired })
    worker.respond({ type: 'result', requestId: (await nextMessage(2)).requestId })
    const expiredB = { ...expired, modelId: 'm2' }
    worker.respond({ type: 'error', requestId: (await nextMessage(3)).requestId, ...expiredB })
    const update = await nextMessage(4)
    expect(update.payload).toEqual({
      method: 'setSourceUrl',
      args: ['m2', 'https://bucket/m2?sig=2'],
    })
    worker.respond({ type: 'result', requestId: update.requestId })
    worker.respond({ type: 'result', requestId: (await nextMessage(5)).requestId, data: ['d'] })

    await expect(result).resolves.toEqual(['d'])
    expect(sourceUrls.renew.mock.calls).toEqual([
      ['m1', rangeSource.url],
      ['m2', 'https://bucket/b?sig=1'],
    ])
  })

  it('surfaces storage that stopped honouring Range without renewing or retrying', async () => {
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({
      type: 'error',
      requestId: (await nextMessage(1)).requestId,
      code: SNAPSHOT_RANGE_UNSUPPORTED,
      modelId: 'm1',
      error: 'Storage stopped honouring Range requests',
    })

    await expect(result).rejects.toBeInstanceOf(SnapshotRangeUnsupportedError)
    await expect(result).rejects.toMatchObject({
      modelId: 'm1',
      message: 'Storage stopped honouring Range requests',
    })
    expect(sourceUrls.renew).not.toHaveBeenCalled()
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
  })

  it('hands an aged URL to the worker before the call', async () => {
    await initialized()
    sourceUrls.get.mockResolvedValue('https://bucket/a?sig=3')
    const result = proxy.getDynamicMetricsNames()

    const update = await nextMessage(1)
    expect(update.payload).toEqual({
      method: 'setSourceUrl',
      args: ['m1', 'https://bucket/a?sig=3'],
    })
    worker.respond({ type: 'result', requestId: update.requestId })
    const call = await nextMessage(2)
    expect(call.payload.method).toBe('getDynamicMetricsNames')
    worker.respond({ type: 'result', requestId: call.requestId, data: [] })

    await expect(result).resolves.toEqual([])
    expect(sourceUrls.renew).not.toHaveBeenCalled()
  })

  const openFailure = (modelId: string, code: string) => ({
    modelId,
    error: { code, message: 'Snapshot request failed' },
  })

  it('renews only the model whose source failed at open and reopens only that one', async () => {
    const sourceB = { ...rangeSource, url: 'https://bucket/b?sig=1' }
    sourceUrls.renew.mockImplementation(async (id) => `https://bucket/${id}?sig=2`)
    const init = proxy.init([
      { modelId: 'm1', source: rangeSource },
      { modelId: 'm2', source: sourceB },
      { modelId: 'm3', source: { ...rangeSource, url: 'https://bucket/c?sig=1' } },
    ])

    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m2', SNAPSHOT_SOURCE_EXPIRED), openFailure('m3', 'snapshot-format')],
    })
    const reopen = await nextMessage(1)
    expect(reopen).toEqual({
      type: 'reopen',
      requestId: expect.any(String),
      payload: { modelId: 'm2', source: { url: 'https://bucket/m2?sig=2' } },
    })
    worker.respond({ type: 'result', requestId: reopen.requestId, data: [] })

    await expect(init).resolves.toBeUndefined()
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(sourceUrls.renew).toHaveBeenCalledWith('m2', 'https://bucket/b?sig=1')
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
  })

  it('does not renew a failed open twice: a second failure stays that model status', async () => {
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })
    const reopen = await nextMessage(1)
    worker.respond({
      type: 'result',
      requestId: reopen.requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })

    await expect(init).resolves.toBeUndefined()
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
  })

  it('resolves init when renewing a failed open fails; the open failure stays the status', async () => {
    sourceUrls.renew.mockRejectedValue(new Error('Renewal failed'))
    const init = proxy.init([
      { modelId: 'm1', source: rangeSource },
      { modelId: 'm2', source: { ...rangeSource, url: 'https://bucket/b?sig=1' } },
    ])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })

    await expect(init).resolves.toBeUndefined()
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledOnce()
  })

  it('does not reopen when the renewal of a failed open hands back the failed URL', async () => {
    sourceUrls.renew.mockResolvedValue(rangeSource.url)
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })

    await expect(init).resolves.toBeUndefined()
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledOnce()
  })

  it('reopens once with the same URL after a transient failure at open when it is handed back', async () => {
    sourceUrls.renew.mockResolvedValue(rangeSource.url)
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [{ ...openFailure('m1', SNAPSHOT_SOURCE_EXPIRED), transient: true }],
    })
    const reopen = await nextMessage(1)
    expect(reopen.payload).toEqual({ modelId: 'm1', source: { url: rangeSource.url } })
    worker.respond({
      type: 'result',
      requestId: reopen.requestId,
      data: [{ ...openFailure('m1', SNAPSHOT_SOURCE_EXPIRED), transient: true }],
    })

    await expect(init).resolves.toBeUndefined()
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
  })

  it('resolves init when the renewed location carries a header that is not allowed', async () => {
    const renew = sourceUrls.renew as unknown as Mock<() => Promise<SnapshotSourceRef>>
    renew.mockResolvedValue({ url: 'https://bucket/a', headers: { 'X-Api-Key': 'secret' } })
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })

    await expect(init).resolves.toBeUndefined()
    expect(worker.postMessage).toHaveBeenCalledOnce()
  })

  it('resolves init when the worker rejects the reopen', async () => {
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })
    const reopen = await nextMessage(1)
    worker.respond({ type: 'error', requestId: reopen.requestId, error: 'Reopen failed' })

    await expect(init).resolves.toBeUndefined()
  })

  it('still rejects init when it is aborted during a renewal', async () => {
    const controller = new AbortController()
    sourceUrls.renew.mockImplementation(async () => {
      controller.abort()
      return 'https://bucket/a?sig=2'
    })
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }], controller.signal)
    worker.respond({
      type: 'result',
      requestId: (await nextMessage(0)).requestId,
      data: [openFailure('m1', SNAPSHOT_SOURCE_EXPIRED)],
    })

    await expect(init).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('always transfers snapshot buffers on init, as no init is retried', async () => {
    const buffer = new ArrayBuffer(8)
    const other = new ArrayBuffer(8)
    const plain = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const plainInit = plain.init([{ modelId: 'z', buffer }]).catch(() => undefined)
    expect(worker.postMessage.mock.calls[0]![1]).toEqual([buffer])

    const rangeInit = proxy
      .init([
        { modelId: 'y', buffer: other },
        { modelId: 'm1', source: rangeSource },
      ])
      .catch(() => undefined)
    expect(worker.postMessage.mock.calls[1]![1]).toEqual([other])
    plain.terminate()
    proxy.terminate()
    await Promise.all([plainInit, rangeInit])
  })

  it('keeps URLs out of the message of a worker error', async () => {
    await initialized()
    const failing = proxy.getUniqueDatasetsIds()
    worker.respond({
      type: 'error',
      requestId: (await nextMessage(1)).requestId,
      error: "Failed to load 'https://bucket/a?X-Amz-Signature=SECRET'; Bearer tok-SECRET",
    })
    const error = (await failing.catch((caught: unknown) => caught)) as Error
    expect(error.message).not.toMatch(/SECRET|\?/)
    expect(error.message).toContain('https://bucket')
  })

  it('does not renew for ordinary errors or without a URL provider', async () => {
    await initialized()
    const failing = proxy.getUniqueDatasetsIds()
    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, error: 'bad' })
    await expect(failing).rejects.toMatchObject({ message: 'bad' })

    const plain = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const call = plain.getUniqueDatasetsIds()
    worker.respond({ type: 'error', requestId: (await nextMessage(2)).requestId, ...expired })
    await expect(call).rejects.toMatchObject({ code: SNAPSHOT_SOURCE_EXPIRED, modelId: 'm1' })
    expect(sourceUrls.renew).not.toHaveBeenCalled()
  })
})

describe('ExperimentSnapshotWorkerProxy sources with headers', () => {
  const url = 'https://workspace.test/api/2.0/fs/files/a.tar'
  const tokenSource = (token: string) => ({ url, headers: { Authorization: `Bearer ${token}` } })
  const rangeSource = { kind: 'range', ...tokenSource('t1'), offset: 512, size: 4096 } as const
  const expired = { code: SNAPSHOT_SOURCE_EXPIRED, modelId: 'm1', error: 'status 401' }
  let worker: FakeWorker
  let sourceUrls: {
    get: Mock<(id: string) => Promise<SnapshotSourceRef>>
    renew: Mock<(id: string, failed: SnapshotSourceRef) => Promise<SnapshotSourceRef>>
  }
  let proxy: ExperimentSnapshotWorkerProxy

  async function nextMessage(index: number) {
    await vi.waitFor(() => expect(worker.postMessage.mock.calls.length).toBeGreaterThan(index))
    return worker.postMessage.mock.calls[index]![0]
  }

  beforeEach(async () => {
    worker = new FakeWorker()
    sourceUrls = {
      get: vi.fn(async () => tokenSource('t1')),
      renew: vi.fn(async () => tokenSource('t2')),
    }
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, { sourceUrls })
    const init = proxy.init([{ modelId: 'm1', source: rangeSource }])
    worker.respond({ type: 'result', requestId: (await nextMessage(0)).requestId, data: true })
    await init
  })

  it('renews an expired token for the same URL and hands the new headers to the worker', async () => {
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...expired })
    const update = await nextMessage(2)
    expect(update.payload).toEqual({ method: 'setSourceUrl', args: ['m1', tokenSource('t2')] })
    worker.respond({ type: 'result', requestId: update.requestId })
    worker.respond({ type: 'result', requestId: (await nextMessage(3)).requestId, data: ['d'] })

    await expect(result).resolves.toEqual(['d'])
    expect(sourceUrls.renew).toHaveBeenCalledExactlyOnceWith('m1', tokenSource('t1'))
  })

  it('sends nothing for an equal location, and an aged token when it changed', async () => {
    const unchanged = proxy.getDynamicMetricsNames()
    const call = await nextMessage(1)
    expect(call.payload.method).toBe('getDynamicMetricsNames')
    worker.respond({ type: 'result', requestId: call.requestId, data: [] })
    await unchanged

    sourceUrls.get.mockResolvedValue(tokenSource('t3'))
    const aged = proxy.getDynamicMetricsNames()
    const update = await nextMessage(2)
    expect(update.payload).toEqual({ method: 'setSourceUrl', args: ['m1', tokenSource('t3')] })
    worker.respond({ type: 'result', requestId: update.requestId })
    worker.respond({ type: 'result', requestId: (await nextMessage(3)).requestId, data: [] })
    await aged
    expect(sourceUrls.renew).not.toHaveBeenCalled()
  })

  it.each([
    [SNAPSHOT_SOURCE_REDIRECT, SnapshotSourceRedirectError, {}],
    [SNAPSHOT_SOURCE_TOO_LARGE, SnapshotSourceTooLargeError, { size: 2048, limit: 1024 }],
    [
      SNAPSHOT_TOO_LARGE_FOR_BROWSER,
      SnapshotTooLargeForBrowserError,
      { size: 2 ** 32 - 1, limit: 2 ** 31 },
    ],
  ] as const)('rebuilds %s from the worker and does not renew it', async (code, type, extra) => {
    const result = proxy.getUniqueDatasetsIds()

    const failure = { code, modelId: 'm1', error: 'failed', ...extra }
    worker.respond({ type: 'error', requestId: (await nextMessage(1)).requestId, ...failure })

    await expect(result).rejects.toBeInstanceOf(type)
    await expect(result).rejects.toMatchObject({ modelId: 'm1', ...extra })
    expect(sourceUrls.renew).not.toHaveBeenCalled()
  })
})

/** Answers calls in arrival order, with one trace page cursor as the provider keeps it. */
class OrderedWorker extends EventTarget {
  readonly messages: { type: string; requestId: string; payload?: any; [key: string]: any }[] = []
  readonly terminate = vi.fn()
  /** Methods whose answers are held back until `release` is called. */
  readonly held = new Set<string>()
  private readonly waiting: (() => void)[] = []
  private page = 0

  get methods(): string[] {
    return this.messages
      .filter((message) => message.type !== 'cancel')
      .map((message) => (message.type === 'call' ? message.payload.method : message.type))
  }

  postMessage(message: { type: string; requestId: string; payload?: any }) {
    this.messages.push(message)
    if (message.type === 'cancel') return
    const method = message.type === 'call' ? message.payload.method : message.type
    let data: unknown = method === 'init' ? [] : undefined
    if (method === 'setSourceUrl') data = true
    if (method === 'resetTracesRequestParams') this.page = 0
    if (method === 'getTraces') data = [`row-page-${++this.page}`]
    const answer = () =>
      this.dispatchEvent(
        new MessageEvent('message', {
          data: { type: 'result', requestId: message.requestId, data },
        }),
      )
    if (this.held.has(method)) this.waiting.push(answer)
    else queueMicrotask(answer)
  }

  release() {
    this.waiting.splice(0).forEach((answer) => answer())
  }
}

describe('ExperimentSnapshotWorkerProxy call order', () => {
  const rangeSource = {
    kind: 'range',
    url: 'https://bucket/a?sig=1',
    offset: 0,
    size: 4096,
  } as const
  const traceParams = { sort_by: 'created_at', order: 'desc', limit: 1 } as any
  let worker: OrderedWorker
  let current: string
  let proxy: ExperimentSnapshotWorkerProxy

  beforeEach(async () => {
    worker = new OrderedWorker()
    current = rangeSource.url
    const sourceUrls = {
      get: vi.fn(async () => current),
      renew: vi.fn(async () => 'https://bucket/a?sig=9'),
    }
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, { sourceUrls })
    await proxy.init([{ modelId: 'm1', source: rangeSource }])
  })

  it('posts a paging reset before the read made after it, while an aged URL is handed over', async () => {
    await proxy.getTraces(traceParams)
    await proxy.getTraces(traceParams)
    current = 'https://bucket/a?sig=2'

    // As the trace store resets: the reset is not awaited before the first page is read.
    void proxy.resetTracesRequestParams()
    const firstPage = await proxy.getTraces(traceParams)
    const secondPage = await proxy.getTraces(traceParams)

    expect(worker.methods.slice(3, 6)).toEqual([
      'setSourceUrl',
      'resetTracesRequestParams',
      'getTraces',
    ])
    expect([firstPage, secondPage]).toEqual([['row-page-1'], ['row-page-2']])
  })

  it('posts calls made back to back in call order while a URL refresh is pending', async () => {
    current = 'https://bucket/a?sig=2'
    const calls = [
      proxy.resetTracesRequestParams(),
      proxy.getUniqueDatasetsIds(),
      proxy.getTraces(traceParams),
      proxy.resetEvalsDatasetsRequestParams(),
      proxy.getDynamicMetricsNames(),
    ]

    await Promise.all(calls)

    expect(worker.methods.slice(1)).toEqual([
      'setSourceUrl',
      'resetTracesRequestParams',
      'getUniqueDatasetsIds',
      'getTraces',
      'resetEvalsDatasetsRequestParams',
      'getDynamicMetricsNames',
    ])
  })

  it('does not hold back the posting of a later call behind a slow answer', async () => {
    worker.held.add('getUniqueDatasetsIds')
    const slow = proxy.getUniqueDatasetsIds()

    await expect(proxy.getTraces(traceParams)).resolves.toEqual(['row-page-1'])
    worker.release()
    await slow
    expect(worker.methods.slice(1)).toEqual(['getUniqueDatasetsIds', 'getTraces'])
  })

  it('tells the worker when the caller of each call gives up', async () => {
    const before = Date.now()
    await proxy.getUniqueDatasetsIds()
    const [call] = worker.messages.filter((message) => message.type === 'call')

    expect(call!.deadline).toBeGreaterThanOrEqual(before + 60_000)
    expect(call!.deadline).toBeLessThanOrEqual(Date.now() + 60_000)
  })

  it('posts the limit of a caller that gives up before this proxy does', async () => {
    const before = Date.now()
    await proxy.getMetricBuckets({ keys: ['loss'], level: 0 }, undefined, { timeoutMs: 30_000 })
    await proxy.getMetricCatalogs(undefined, undefined, { timeoutMs: 90_000 })
    const [buckets, catalogs] = worker.messages.filter((message) => message.type === 'call')

    expect(buckets!.deadline).toBeGreaterThanOrEqual(before + 30_000)
    expect(buckets!.deadline).toBeLessThanOrEqual(Date.now() + 30_000)
    expect(catalogs!.deadline).toBeLessThanOrEqual(Date.now() + 60_000)
  })

  it('fails a call whose URL lookup hangs at its deadline, and posts the next call', async () => {
    vi.useFakeTimers()
    const hung = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, {
      sourceUrls: {
        get: vi
          .fn<() => Promise<string>>()
          .mockReturnValueOnce(new Promise(() => undefined))
          .mockImplementation(async () => current),
        renew: vi.fn(async () => current),
      },
    })
    const init = hung.init([{ modelId: 'm1', source: rangeSource }])
    await vi.advanceTimersByTimeAsync(0)
    await init

    const stuck = hung.getMetricBuckets({ keys: ['loss'], level: 0 }, undefined, {
      timeoutMs: 30_000,
    })
    const rejected = expect(stuck).rejects.toThrow(/timed out/)
    const next = hung.getTraces(traceParams)
    await vi.advanceTimersByTimeAsync(30_000)

    await rejected
    await expect(next).resolves.toEqual(['row-page-1'])
    expect(worker.methods.filter((method) => method === 'getMetricBuckets')).toEqual([])
    vi.useRealTimers()
  })
})

describe('ExperimentSnapshotWorkerProxy statuses', () => {
  it('tells its listeners when a call changed the statuses, in an answer or an error', async () => {
    const worker = new FakeWorker()
    const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const listener = vi.fn()
    const stop = proxy.onStatusesChanged(listener)

    const answered = proxy.getUniqueDatasetsIds()
    const first = worker.postMessage.mock.calls[0]![0]
    worker.respond({ type: 'result', requestId: first.requestId, data: [], statusesChanged: true })
    await answered
    const plain = proxy.getUniqueDatasetsIds()
    worker.respond({ type: 'result', requestId: worker.postMessage.mock.calls[1]![0].requestId })
    await plain
    const failed = proxy.getUniqueDatasetsIds()
    const third = worker.postMessage.mock.calls[2]![0]
    worker.respond({ type: 'error', requestId: third.requestId, error: 'x', statusesChanged: true })
    await expect(failed).rejects.toThrow('x')
    stop()
    const unheard = proxy.getUniqueDatasetsIds()
    const fourth = worker.postMessage.mock.calls[3]![0]
    worker.respond({ type: 'result', requestId: fourth.requestId, data: [], statusesChanged: true })
    await unheard

    expect(listener).toHaveBeenCalledTimes(2)
  })
})

describe('ExperimentSnapshotWorkerProxy comparisons', () => {
  const sourceOf = (modelId: string) =>
    ({ kind: 'range', url: `https://bucket/${modelId}?sig=1`, offset: 0, size: 4096 }) as const
  const forbidden = {
    type: 'error',
    code: SNAPSHOT_SOURCE_EXPIRED,
    modelId: 'm2',
    status: 403,
    isolatable: true,
    error: 'Range request returned status 403',
  }
  let worker: FakeWorker
  let sourceUrls: {
    get: Mock<(id: string) => Promise<string>>
    renew: Mock<(id: string, failedUrl: string) => Promise<string>>
  }
  let proxy: ExperimentSnapshotWorkerProxy

  const calls = () => worker.postMessage.mock.calls.map(([message]) => message)

  async function nextMessage(index: number) {
    await vi.waitFor(() => expect(worker.postMessage.mock.calls.length).toBeGreaterThan(index))
    return worker.postMessage.mock.calls[index]![0]
  }

  async function initialized(failures: unknown[] = []) {
    const init = proxy.init(['m1', 'm2'].map((modelId) => ({ modelId, source: sourceOf(modelId) })))
    worker.respond({ type: 'result', requestId: (await nextMessage(0)).requestId, data: failures })
    await init
  }

  beforeEach(() => {
    worker = new FakeWorker()
    sourceUrls = {
      get: vi.fn(async (id: string) => sourceOf(id).url),
      renew: vi.fn(async (id: string) => sourceOf(id).url),
    }
    proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, { sourceUrls })
  })

  it('leaves out an experiment whose failure stands, without reading it again', async () => {
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    const first = await nextMessage(1)
    expect(first.context).toEqual({ renewableSources: ['m1', 'm2'], failedSources: [] })
    worker.respond({ ...forbidden, requestId: first.requestId })
    const retry = await nextMessage(2)
    expect(retry.payload).toEqual(first.payload)
    expect(retry.context).toEqual({
      renewableSources: ['m1'],
      failedSources: [
        { modelId: 'm2', error: { code: SNAPSHOT_SOURCE_EXPIRED, message: forbidden.error } },
      ],
    })
    worker.respond({ type: 'result', requestId: retry.requestId, data: ['d1'] })

    await expect(result).resolves.toEqual(['d1'])
    expect(sourceUrls.renew).toHaveBeenCalledExactlyOnceWith('m2', sourceOf('m2').url)
    expect(calls()).toHaveLength(3)
  })

  it('leaves out only the experiment whose URL could not be renewed', async () => {
    sourceUrls.renew.mockRejectedValue(new Error('Request failed with status 404'))
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({ ...forbidden, status: undefined, requestId: (await nextMessage(1)).requestId })
    const retry = await nextMessage(2)
    worker.respond({ type: 'result', requestId: retry.requestId, data: ['d1'] })

    await expect(result).resolves.toEqual(['d1'])
    expect(retry.context.failedSources.map(({ modelId }: { modelId: string }) => modelId)).toEqual([
      'm2',
    ])
  })

  it('still rejects the call when the failure cannot be left out', async () => {
    await initialized()
    const result = proxy.getUniqueDatasetsIds()

    worker.respond({
      ...forbidden,
      isolatable: undefined,
      requestId: (await nextMessage(1)).requestId,
    })

    await expect(result).rejects.toMatchObject({ code: SNAPSHOT_SOURCE_EXPIRED, status: 403 })
    expect(calls()).toHaveLength(2)
  })

  it('does not fail a call when the URL lookup of one experiment fails', async () => {
    await initialized()
    sourceUrls.get.mockImplementation(async (id) => {
      if (id === 'm2') throw new Error('Request failed with status 404')
      return sourceOf(id).url
    })

    const result = proxy.getUniqueDatasetsIds()
    worker.respond({ type: 'result', requestId: (await nextMessage(1)).requestId, data: ['d1'] })

    await expect(result).resolves.toEqual(['d1'])
  })

  it('never looks up or sends the URL of an experiment that did not open', async () => {
    await initialized([
      { modelId: 'm2', error: { code: SNAPSHOT_SOURCE_EXPIRED, message: 'denied' } },
    ])
    expect(sourceUrls.renew).toHaveBeenCalledOnce()
    sourceUrls.get.mockClear()

    const result = proxy.getUniqueDatasetsIds()
    const call = await nextMessage(1)
    worker.respond({ type: 'result', requestId: call.requestId, data: ['d1'] })

    await expect(result).resolves.toEqual(['d1'])
    expect(sourceUrls.get.mock.calls).toEqual([['m1']])
    expect(call.context.renewableSources).toEqual(['m1'])
  })

  it('stops sending the URL of an experiment that the worker loaded in full', async () => {
    await initialized()
    sourceUrls.get.mockImplementation(async (id) => `https://bucket/${id}?sig=2`)

    const first = proxy.getUniqueDatasetsIds()
    const updates = [await nextMessage(1), await nextMessage(2)]
    expect(updates.map((message) => message.payload.args[0])).toEqual(['m1', 'm2'])
    worker.respond({ type: 'result', requestId: updates[0].requestId, data: true })
    worker.respond({ type: 'result', requestId: updates[1].requestId, data: false })
    worker.respond({ type: 'result', requestId: (await nextMessage(3)).requestId, data: [] })
    await first

    sourceUrls.get.mockImplementation(async (id) => `https://bucket/${id}?sig=3`)
    const second = proxy.getUniqueDatasetsIds()
    const update = await nextMessage(4)
    expect(update.payload.args[0]).toBe('m1')
    worker.respond({ type: 'result', requestId: update.requestId, data: true })
    const call = await nextMessage(5)
    expect(call.payload.method).toBe('getUniqueDatasetsIds')
    worker.respond({ type: 'result', requestId: call.requestId, data: [] })
    await second
  })
})
