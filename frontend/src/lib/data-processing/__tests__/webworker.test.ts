import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it, vi, type Mock } from 'vitest'

const source = readFileSync('public/webworker.js', 'utf8')

const interruptedResponse = {
  status: 'error',
  error_type: 'KeyboardInterrupt',
  error_message: 'Execution interrupted by user',
}

function createRunningRoute() {
  let finish!: (value: unknown) => void
  let fail!: (error: Error) => void
  const result = new Promise((resolve, reject) => {
    finish = resolve
    fail = reject
  })
  const task = {
    cancel: vi.fn(() =>
      fail(Object.assign(new Error('Task was cancelled'), { type: 'CancelledError' })),
    ),
  }
  return { result, task, finish }
}

function pyimportWith(invoke: unknown, tasks: { cancel: Mock }[]) {
  return (name: string) => {
    if (name === 'asyncio') return { all_tasks: () => tasks }
    if (name === 'micropip') return { install: vi.fn() }
    return { invoke }
  }
}

function startWorker() {
  const postMessage = vi.fn()
  const invoke = vi.fn(async (): Promise<unknown> => ({ toJs: () => ({ status: 'success' }) }))
  const tasks: { cancel: Mock }[] = []
  const nativeFetch = vi.fn(async (_input: string, _init: { signal: AbortSignal }) => 'response')
  const self = {
    postMessage,
    onmessage: null as unknown as (event: object) => Promise<void>,
    fetch: nativeFetch as (input: string, init?: { signal?: AbortSignal }) => Promise<string>,
  }
  runInNewContext(source, {
    self,
    importScripts: vi.fn(),
    loadPyodide: async () => ({
      loadPackage: vi.fn(),
      pyimport: pyimportWith(invoke, tasks),
    }),
    Error,
    AbortController,
    AbortSignal,
  })
  return { self, postMessage, invoke, tasks, nativeFetch }
}

const route = { message: 'invokeRoute', payload: { route: '/pyfunc/compute', data: {} } }

describe('Pyodide worker initialization failures', () => {
  it.each(['script', 'runtime'])(
    'replies to every caller when the CDN %s fails',
    async (failure) => {
      const postMessage = vi.fn()
      const self = { postMessage, onmessage: null as unknown as (event: object) => Promise<void> }
      runInNewContext(source, {
        self,
        importScripts: () => {
          if (failure === 'script') throw new Error('CDN blocked')
        },
        loadPyodide: async () => {
          throw new Error('CDN blocked')
        },
        Error,
        AbortController,
        AbortSignal,
      })
      for (const [id, message] of ['LOAD_PYODIDE', 'invokeRoute', 'interrupt'].entries()) {
        await self.onmessage({ data: { id, message } })
        expect(postMessage).toHaveBeenLastCalledWith({ id, message, error: 'CDN blocked' })
      }
      expect(postMessage).toHaveBeenCalledTimes(3)
    },
  )

  it('reports failed package downloads to the frontend without leaving requests pending', async () => {
    const postMessage = vi.fn()
    const self = { postMessage, onmessage: null as unknown as (event: object) => Promise<void> }
    runInNewContext(source, {
      self,
      importScripts: vi.fn(),
      loadPyodide: async () => ({
        loadPackage: async () => {
          throw new Error('Package download failed')
        },
      }),
      Error,
      AbortController,
      AbortSignal,
    })
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    expect(postMessage).toHaveBeenCalledWith({
      id: 1,
      message: 'LOAD_PYODIDE',
      error: 'Package download failed',
    })
  })
})

describe('Pyodide worker request failures', () => {
  it.each(['invokeRoute', 'tabular_train', 'tabular_predict', 'tabular_deallocate', 'unknown'])(
    'replies with an error when %s fails and still handles subsequent requests',
    async (message) => {
      const postMessage = vi.fn()
      const self = {
        postMessage,
        onmessage: null as unknown as (event: object) => Promise<void>,
        pyodideReadyPromise: Promise.resolve(true),
        pyodide: {},
      }
      runInNewContext(source, {
        self,
        importScripts: vi.fn(),
        loadPyodide: () => new Promise(() => {}),
        Error,
        AbortController,
        AbortSignal,
      })
      self.pyodideReadyPromise = Promise.resolve(true)
      self.pyodide = {
        pyimport: pyimportWith(async () => {
          throw new Error('Python failed')
        }, []),
      }
      await self.onmessage({ data: { id: 1, message, payload: { route: '/train', data: {} } } })
      expect(postMessage).toHaveBeenCalledExactlyOnceWith({
        id: 1,
        message,
        error: message === 'unknown' ? 'Unknown webworker message: unknown' : 'Python failed',
      })
      await self.onmessage({ data: { id: 2, message: 'LOAD_PYODIDE' } })
      expect(postMessage).toHaveBeenLastCalledWith({
        id: 2,
        message: 'LOAD_PYODIDE',
        payload: true,
      })
    },
  )
})

describe('worker cleanup responses', () => {
  it.each([null, undefined])(
    'returns a null payload for a successful Python store deletion (%s)',
    async (response) => {
      const { self, postMessage, invoke } = startWorker()
      invoke.mockResolvedValue(response)
      await self.onmessage({
        data: {
          id: 1,
          message: 'invokeRoute',
          payload: { route: '/store/deallocate', data: { key: 'model' } },
        },
      })
      expect(invoke).toHaveBeenCalledWith('/store/deallocate', { key: 'model' })
      expect(postMessage).toHaveBeenCalledWith({ id: 1, message: 'invokeRoute', payload: null })
    },
  )
})

describe('route cancellation', () => {
  it('cancels the running task and reports the route as interrupted', async () => {
    const { self, postMessage, invoke, tasks } = startWorker()
    const running = createRunningRoute()
    invoke.mockReturnValueOnce(running.result)
    tasks.push(running.task)
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    const computation = self.onmessage({ data: { ...route, id: 2 } })
    await self.onmessage({ data: { id: 3, message: 'interrupt' } })
    await computation
    expect(running.task.cancel).toHaveBeenCalledOnce()
    expect(postMessage).toHaveBeenCalledWith({ id: 3, message: 'interrupt', payload: true })
    expect(postMessage).toHaveBeenCalledWith({
      id: 2,
      message: 'invokeRoute',
      payload: interruptedResponse,
    })
  })

  it('cancels every running task', async () => {
    const { self, invoke, tasks } = startWorker()
    const first = createRunningRoute()
    const second = createRunningRoute()
    invoke.mockReturnValueOnce(first.result).mockReturnValueOnce(second.result)
    tasks.push(first.task, second.task)
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    const computations = [
      self.onmessage({ data: { ...route, id: 2 } }),
      self.onmessage({ data: { ...route, id: 3 } }),
    ]
    await self.onmessage({ data: { id: 4, message: 'interrupt' } })
    await Promise.all(computations)
    expect(first.task.cancel).toHaveBeenCalledOnce()
    expect(second.task.cancel).toHaveBeenCalledOnce()
  })

  it.each(['invokeRoute', 'tabular_train', 'tabular_predict', 'tabular_deallocate'])(
    'does not carry an idle interruption into the next %s',
    async (message) => {
      const { self, postMessage, invoke } = startWorker()
      await self.onmessage({ data: { id: 1, message: 'interrupt' } })
      await self.onmessage({ data: { id: 2, message: 'interrupt' } })
      await self.onmessage({
        data: { id: 3, message, payload: { route: '/pyfunc/compute', data: {} } },
      })
      expect(invoke).toHaveBeenCalledOnce()
      expect(postMessage).toHaveBeenLastCalledWith({
        id: 3,
        message,
        payload: { status: 'success' },
      })
    },
  )

  it('runs the next route normally after a cancellation', async () => {
    const { self, postMessage, invoke, tasks } = startWorker()
    const running = createRunningRoute()
    invoke.mockReturnValueOnce(running.result)
    tasks.push(running.task)
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    const computation = self.onmessage({ data: { ...route, id: 2 } })
    await self.onmessage({ data: { id: 3, message: 'interrupt' } })
    await computation
    tasks.length = 0
    await self.onmessage({ data: { ...route, id: 4 } })
    expect(postMessage).toHaveBeenLastCalledWith({
      id: 4,
      message: 'invokeRoute',
      payload: { status: 'success' },
    })
  })

  it('does not treat other Python errors as an interruption', async () => {
    const { self, postMessage, invoke } = startWorker()
    invoke.mockRejectedValueOnce(Object.assign(new Error('Bad data'), { type: 'ValueError' }))
    await self.onmessage({ data: { ...route, id: 1 } })
    expect(postMessage).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      message: 'invokeRoute',
      error: 'Bad data',
    })
  })

  it('aborts running requests and leaves finished and later ones alone', async () => {
    const { self, nativeFetch } = startWorker()
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    await self.fetch('/finished')
    nativeFetch.mockReturnValueOnce(new Promise<string>(() => {}))
    void self.fetch('/running')
    await self.onmessage({ data: { id: 2, message: 'interrupt' } })
    await self.fetch('/later')
    const signals = nativeFetch.mock.calls.map(([, init]) => init.signal.aborted)
    expect(signals).toEqual([false, true, false])
  })

  it('aborts the newest requests first so queued ones never start', async () => {
    const { self, nativeFetch } = startWorker()
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    const aborted: string[] = []
    nativeFetch.mockImplementation((input, init) => {
      init.signal.addEventListener('abort', () => aborted.push(input))
      return new Promise<string>(() => {})
    })
    void self.fetch('/oldest')
    void self.fetch('/newest')
    await self.onmessage({ data: { id: 2, message: 'interrupt' } })
    expect(aborted).toEqual(['/newest', '/oldest'])
  })

  it('keeps the abort signal passed by the caller', async () => {
    const { self, nativeFetch } = startWorker()
    const caller = new AbortController()
    nativeFetch.mockReturnValueOnce(new Promise<string>(() => {}))
    void self.fetch('/request', { signal: caller.signal })
    expect(nativeFetch.mock.calls[0][1].signal.aborted).toBe(false)
    caller.abort()
    expect(nativeFetch.mock.calls[0][1].signal.aborted).toBe(true)
  })

  it('replies with an error when cancellation fails', async () => {
    const { self, postMessage, invoke, tasks } = startWorker()
    const running = createRunningRoute()
    running.task.cancel.mockImplementationOnce(() => {
      throw new Error('Cancel failed')
    })
    invoke.mockReturnValueOnce(running.result)
    tasks.push(running.task)
    await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
    const computation = self.onmessage({ data: { ...route, id: 2 } })
    await self.onmessage({ data: { id: 3, message: 'interrupt' } })
    expect(postMessage).toHaveBeenLastCalledWith({
      id: 3,
      message: 'interrupt',
      error: 'Cancel failed',
    })
    running.finish({ toJs: () => ({ status: 'success' }) })
    await computation
  })
})
