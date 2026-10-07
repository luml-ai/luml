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

afterEach(() => vi.unstubAllGlobals())

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
})
