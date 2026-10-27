import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Tasks, WEBWORKER_ROUTES_ENUM, WebworkerMessage } from '../interfaces'

type Request = {
  id: number
  message: WebworkerMessage
  payload: { route?: WEBWORKER_ROUTES_ENUM; data?: unknown }
}

class FakeWorker {
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: ErrorEvent) => void) | null = null
  onmessageerror: ((event: MessageEvent) => void) | null = null
  postMessage = vi.fn<(request: Request) => void>()
  terminate = vi.fn()

  respond(payload: unknown, request = this.postMessage.mock.calls.at(-1)![0], error?: string) {
    this.onmessage?.({ data: { id: request.id, payload, error } } as MessageEvent)
  }
}

let workers: FakeWorker[]
let workerConstructor: ReturnType<typeof vi.fn>
let service: typeof import('../DataProcessingWorker').DataProcessingWorker

beforeEach(async () => {
  vi.resetModules()
  workers = []
  workerConstructor = vi.fn(function () {
    const worker = new FakeWorker()
    workers.push(worker)
    return worker
  })
  vi.stubGlobal('Worker', workerConstructor)
  service = (await import('../DataProcessingWorker')).DataProcessingWorker
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const entries = [
  [
    'training',
    () =>
      service.startTraining(
        { data: {}, target: 'y', task: Tasks.TABULAR_REGRESSION },
        WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN,
      ),
  ],
  [
    'prediction',
    () =>
      service.startPredict({ data: {}, model_id: 'model' }, WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT),
  ],
  ['python model initialization', () => service.initPythonModel(new ArrayBuffer(1))],
  [
    'python model computation',
    () => service.computePythonModel({ model_id: 'model', inputs: {}, dynamic_attributes: {} }),
  ],
  [
    'model deallocation',
    () => service.deallocateModels(['model'], WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE),
  ],
  ['python model deinitialization', () => service.deinitPythonModel('model')],
  ['interruption', () => service.interrupt()],
  [
    'direct messages',
    () => service.sendMessage(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT),
  ],
] as const

describe('lazy Pyodide initialization', () => {
  it('does not create a worker on import or empty cleanup', async () => {
    await service.deallocateModels([], WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE)
    expect(workerConstructor).not.toHaveBeenCalled()
  })

  it.each(entries)('waits for readiness on first %s', async (_name, invoke) => {
    const pending = invoke()
    await flushPromises()
    expect(workerConstructor).toHaveBeenCalledExactlyOnceWith('/webworker.js')
    const worker = workers[0]
    expect(worker.postMessage).toHaveBeenCalledTimes(1)
    expect(worker.postMessage.mock.calls[0][0].message).toBe(WebworkerMessage.LOAD_PYODIDE)

    worker.respond(true)
    await flushPromises()
    expect(worker.postMessage).toHaveBeenCalledTimes(2)
    worker.respond({ status: 'success' })
    await pending
  })

  it('shares initialization across simultaneous calls and reuses the ready worker', async () => {
    const training = entries[0][1]()
    const prediction = entries[1][1]()
    const initialization = service.initPyodide()
    const readiness = service.checkPyodideReady()
    await flushPromises()
    expect(workerConstructor).toHaveBeenCalledTimes(1)
    const worker = workers[0]
    expect(worker.postMessage).toHaveBeenCalledTimes(1)
    worker.respond(true)
    await flushPromises()
    expect(worker.postMessage).toHaveBeenCalledTimes(3)
    const requests = worker.postMessage.mock.calls.slice(1).map(([request]) => request)
    worker.respond('prediction result', requests[1])
    worker.respond('training result', requests[0])
    await expect(training).resolves.toBe('training result')
    await expect(prediction).resolves.toBe('prediction result')
    await Promise.all([initialization, readiness])

    const next = entries[2][1]()
    await flushPromises()
    expect(workerConstructor).toHaveBeenCalledTimes(1)
    expect(
      worker.postMessage.mock.calls.filter(
        ([request]) => request.message === WebworkerMessage.LOAD_PYODIDE,
      ),
    ).toHaveLength(1)
    worker.respond({ status: 'success', model_id: 'model' })
    await next
  })

  it.each(['negative readiness', 'initialization error', 'worker error'])(
    'rejects concurrent callers after %s and allows retry',
    async (failure) => {
      const pending = Promise.allSettled([entries[0][1](), entries[1][1]()])
      await flushPromises()
      const worker = workers[0]
      if (failure === 'worker error') worker.onerror?.({ message: 'Download failed' } as ErrorEvent)
      else
        worker.respond(
          false,
          undefined,
          failure === 'initialization error' ? 'Download failed' : undefined,
        )
      const results = await pending
      expect(results.every((result) => result.status === 'rejected')).toBe(true)
      expect(worker.terminate).toHaveBeenCalledTimes(1)
      expect(worker.postMessage).toHaveBeenCalledTimes(1)

      const retry = service.checkPyodideReady()
      await flushPromises()
      expect(workerConstructor).toHaveBeenCalledTimes(2)
      workers[1].respond(true)
      await retry
    },
  )

  it('allows retry after worker construction fails', async () => {
    workerConstructor.mockImplementationOnce(() => {
      throw new Error('Worker blocked')
    })
    await expect(service.initPyodide()).rejects.toThrow('Worker blocked')
    const retry = service.initPyodide()
    await flushPromises()
    workers[0].respond(true)
    await retry
  })

  it('rejects outstanding operations if the ready worker crashes', async () => {
    const ready = service.initPyodide()
    await flushPromises()
    workers[0].respond(true)
    await ready
    const pending = Promise.allSettled([entries[0][1](), entries[1][1]()])
    await flushPromises()
    workers[0].onerror?.({ message: 'Worker crashed' } as ErrorEvent)
    expect((await pending).every((result) => result.status === 'rejected')).toBe(true)
  })

  it('times out a stalled initialization, rejects all callers, and allows retry', async () => {
    vi.useFakeTimers()
    const pending = Promise.allSettled([service.checkPyodideReady(), entries[0][1]()])
    await vi.advanceTimersByTimeAsync(120_000)
    const results = await pending
    for (const result of results) {
      expect(result.status).toBe('rejected')
      if (result.status === 'rejected') expect(result.reason.message).toMatch(/timed out/i)
    }
    expect(workers[0].terminate).toHaveBeenCalledTimes(1)
    expect((service as unknown as { callbacks: Map<number, unknown> }).callbacks.size).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    const retry = service.checkPyodideReady()
    workers[1].respond(true)
    await retry
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['error envelope', 'route error', 'empty error envelope'])(
    'rejects an operation after an %s and discards its callback',
    async (failure) => {
      const ready = service.initPyodide()
      workers[0].respond(true)
      await ready
      const pending = entries[0][1]()
      const assertion = expect(pending).rejects.toThrow(/Python failed|Webworker request failed/)
      await flushPromises()
      const worker = workers[0]
      const request = worker.postMessage.mock.calls.at(-1)![0]
      const payload =
        failure === 'route error' ? { status: 'error', error_message: 'Python failed' } : undefined
      worker.respond(
        payload,
        request,
        failure === 'route error' ? undefined : failure === 'error envelope' ? 'Python failed' : '',
      )
      await assertion
      expect((service as unknown as { callbacks: Map<number, unknown> }).callbacks.size).toBe(0)
      worker.respond('late duplicate reply', request)
      expect(worker.terminate).not.toHaveBeenCalled()
      const next = entries[1][1]()
      await flushPromises()
      worker.respond('prediction')
      await expect(next).resolves.toBe('prediction')
    },
  )

  it('rejects all operations on a message decoding failure and allows retry', async () => {
    const ready = service.initPyodide()
    workers[0].respond(true)
    await ready
    const pending = Promise.allSettled([entries[0][1](), entries[1][1]()])
    await flushPromises()
    workers[0].onmessageerror?.({} as MessageEvent)
    const results = await pending
    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect((service as unknown as { callbacks: Map<number, unknown> }).callbacks.size).toBe(0)
    expect(workers[0].terminate).toHaveBeenCalledTimes(1)
    const retry = service.checkPyodideReady()
    workers[1].respond(true)
    await retry
  })

  it('discards the callback when posting a request fails', async () => {
    const ready = service.initPyodide()
    workers[0].respond(true)
    await ready
    workers[0].postMessage.mockImplementationOnce(() => {
      throw new DOMException('Cannot clone request', 'DataCloneError')
    })
    await expect(entries[0][1]()).rejects.toThrow('Cannot clone request')
    expect((service as unknown as { callbacks: Map<number, unknown> }).callbacks.size).toBe(0)
  })
})

describe('model cleanup contracts', () => {
  it.each([
    [WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE, { key: 'model' }, null],
    [WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE, { model_id: 'model' }, { status: 'success' }],
    [WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE, { model_id: 'model' }, { status: 'success' }],
  ])('uses the Python keyword argument for %s', async (route, data, response) => {
    const pending = service.deallocateModels(['model'], route)
    await flushPromises()
    workers[0].respond(true)
    await flushPromises()
    expect(workers[0].postMessage.mock.calls.at(-1)![0].payload).toEqual({ route, data })
    workers[0].respond(response)
    await expect(pending).resolves.toEqual([response])
  })

  it('sends the Python model ID keyword when deinitializing', async () => {
    const pending = service.deinitPythonModel('model')
    await flushPromises()
    workers[0].respond(true)
    await flushPromises()
    expect(workers[0].postMessage.mock.calls.at(-1)![0].payload).toEqual({
      route: WEBWORKER_ROUTES_ENUM.PYFUNC_DEINIT,
      data: { model_id: 'model' },
    })
    workers[0].respond({ status: 'success' })
    await pending
  })

  it.each([
    ['store', () => service.deallocateModels(['model'], WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE)],
    [
      'tabular',
      () => service.deallocateModels(['model'], WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE),
    ],
    [
      'forecasting',
      () => service.deallocateModels(['model'], WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE),
    ],
    ['pyfunc', () => service.deinitPythonModel('model')],
  ])('rejects Python error responses for %s cleanup', async (_name, invoke) => {
    const pending = invoke()
    const rejected = expect(pending).rejects.toThrow('Model not found')
    await flushPromises()
    workers[0].respond(true)
    await flushPromises()
    workers[0].respond({ status: 'error', error_message: 'Model not found' })
    await rejected
  })

  it('attempts every model in a batch even if one fails', async () => {
    const pending = service.deallocateModels(
      ['first', 'second'],
      WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE,
    )
    const rejected = expect(pending).rejects.toThrow('Cleanup failed')
    await flushPromises()
    workers[0].respond(true)
    await flushPromises()
    const requests = workers[0].postMessage.mock.calls.slice(1).map(([request]) => request)
    expect(requests.map((request) => request.payload.data)).toEqual([
      { model_id: 'first' },
      { model_id: 'second' },
    ])
    workers[0].respond({ status: 'error', error_message: 'Cleanup failed' }, requests[0])
    workers[0].respond({ status: 'success' }, requests[1])
    await rejected
  })
})
