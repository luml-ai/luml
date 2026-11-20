import { describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotWorkerProxy } from '../ExperimentSnapshotWorkerProxy'

class FakeWorker extends EventTarget {
  readonly postMessage = vi.fn()
  readonly terminate = vi.fn()

  respond(data: unknown) {
    this.dispatchEvent(new MessageEvent('message', { data }))
  }
}

describe('ExperimentSnapshotWorkerProxy metric bucket methods', () => {
  it.each([
    ['getExperimentStatuses', undefined],
    ['getMetricCatalogs', [{ modelIds: ['m1'], refresh: true }]],
    ['getMetricBuckets', [{ keys: ['loss'], level: 3 }]],
  ] as const)('passes %s through by name', async (method, args) => {
    const worker = new FakeWorker()
    const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const answer = [{ modelId: 'm1', ok: true, value: method }]

    const pending =
      method === 'getMetricBuckets'
        ? proxy.getMetricBuckets(args[0])
        : method === 'getMetricCatalogs'
          ? proxy.getMetricCatalogs(args[0])
          : proxy[method]()
    const [message] = worker.postMessage.mock.calls[0] ?? []
    expect(message).toMatchObject({ type: 'call', payload: { method, args } })
    worker.respond({ type: 'result', requestId: message.requestId, data: answer })

    await expect(pending).resolves.toEqual(answer)
  })

  it('cancels a bucket request in the worker when it is aborted', async () => {
    const worker = new FakeWorker()
    const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const controller = new AbortController()

    const pending = proxy.getMetricBuckets({ keys: ['loss'], level: 3 }, controller.signal)
    controller.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    const [call, cancel] = worker.postMessage.mock.calls.map(([message]) => message)
    expect(cancel).toEqual({ type: 'cancel', requestId: call.requestId })
  })
})
