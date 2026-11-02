import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it, vi } from 'vitest'

const source = readFileSync('public/webworker.js', 'utf8')

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
  it.each([
    'invokeRoute',
    'tabular_train',
    'tabular_predict',
    'tabular_deallocate',
    'interrupt',
    'unknown',
  ])(
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
        SharedArrayBuffer,
      })
      self.pyodideReadyPromise = Promise.resolve(true)
      self.pyodide = {
        pyimport: () => ({
          invoke: async () => {
            throw new Error('Python failed')
          },
        }),
        setInterruptBuffer: () => {
          throw new Error('Interrupt failed')
        },
      }
      await self.onmessage({ data: { id: 1, message, payload: { route: '/train', data: {} } } })
      expect(postMessage).toHaveBeenCalledExactlyOnceWith({
        id: 1,
        message,
        error:
          message === 'unknown'
            ? 'Unknown webworker message: unknown'
            : message === 'interrupt'
              ? 'Interrupt failed'
              : 'Python failed',
      })
      await self.onmessage({ data: { id: 2, message: 'LOAD_PYODIDE' } })
      expect(postMessage).toHaveBeenLastCalledWith({
        id: 2,
        message: 'LOAD_PYODIDE',
        payload: true,
      })
    },
  )

  it('acknowledges interruption', async () => {
    const postMessage = vi.fn()
    const self = {
      postMessage,
      onmessage: null as unknown as (event: object) => Promise<void>,
      pyodideReadyPromise: Promise.resolve(true),
      pyodide: { setInterruptBuffer: vi.fn() },
    }
    runInNewContext(source, {
      self,
      importScripts: vi.fn(),
      loadPyodide: () => new Promise(() => {}),
      SharedArrayBuffer,
      Uint8Array,
    })
    self.pyodideReadyPromise = Promise.resolve(true)
    await self.onmessage({ data: { id: 1, message: 'interrupt' } })
    expect(self.pyodide.setInterruptBuffer).toHaveBeenCalledWith(new Uint8Array([2]))
    expect(postMessage).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      message: 'interrupt',
      payload: true,
    })
  })
})

describe('worker cleanup responses', () => {
  it.each([null, undefined])(
    'returns a null payload for a successful Python store deletion (%s)',
    async (response) => {
      const postMessage = vi.fn()
      const invoke = vi.fn().mockResolvedValue(response)
      const self = { postMessage, onmessage: null as unknown as (event: object) => Promise<void> }
      runInNewContext(source, {
        self,
        importScripts: vi.fn(),
        loadPyodide: async () => ({
          loadPackage: vi.fn(),
          pyimport: (name: string) => (name === 'micropip' ? { install: vi.fn() } : { invoke }),
        }),
        Error,
      })
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

describe('Pyodide interrupt cleanup', () => {
  it.each(['success', 'failure'])(
    'clears a pending interrupt after a route finishes with %s',
    async (outcome) => {
      const postMessage = vi.fn()
      let buffer: Uint8Array | undefined
      let finish!: () => void
      const pending = new Promise<void>((resolve) => {
        finish = resolve
      })
      const invoke = vi
        .fn()
        .mockImplementationOnce(async () => {
          await pending
          if (outcome === 'failure') throw new Error('Interrupted')
          return { toJs: () => ({ status: 'success' }) }
        })
        .mockImplementationOnce(async () => {
          expect(buffer?.[0]).toBe(0)
          return { toJs: () => ({ status: 'success' }) }
        })
      const self = { postMessage, onmessage: null as unknown as (event: object) => Promise<void> }
      runInNewContext(source, {
        self,
        importScripts: vi.fn(),
        loadPyodide: async () => ({
          loadPackage: vi.fn(),
          pyimport: (name: string) => (name === 'micropip' ? { install: vi.fn() } : { invoke }),
          setInterruptBuffer: (value: Uint8Array) => {
            buffer = value
          },
        }),
        SharedArrayBuffer,
        Uint8Array,
        Error,
      })
      const route = { message: 'invokeRoute', payload: { route: '/pyfunc/compute', data: {} } }
      await self.onmessage({ data: { id: 1, message: 'LOAD_PYODIDE' } })
      const computation = self.onmessage({ data: { ...route, id: 2 } })
      await self.onmessage({ data: { id: 3, message: 'interrupt' } })
      expect(buffer?.[0]).toBe(2)
      finish()
      await computation
      expect(buffer?.[0]).toBe(0)
      await self.onmessage({ data: { ...route, id: 4 } })
      expect(postMessage).toHaveBeenLastCalledWith({
        id: 4,
        message: 'invokeRoute',
        payload: { status: 'success' },
      })
    },
  )

  it.each(['invokeRoute', 'tabular_train', 'tabular_predict', 'tabular_deallocate'])(
    'clears idle interrupts before the next %s executes Python',
    async (message) => {
      const postMessage = vi.fn()
      let buffer: Uint8Array | undefined
      const invoke = vi.fn(async () => {
        expect(buffer?.[0]).toBe(0)
        return { toJs: () => ({ status: 'success' }) }
      })
      const self = { postMessage, onmessage: null as unknown as (event: object) => Promise<void> }
      runInNewContext(source, {
        self,
        importScripts: vi.fn(),
        loadPyodide: async () => ({
          loadPackage: vi.fn(),
          pyimport: (name: string) => {
            if (name === 'micropip') return { install: vi.fn() }
            expect(buffer?.[0]).toBe(0)
            return { invoke }
          },
          setInterruptBuffer: (value: Uint8Array) => {
            buffer = value
          },
        }),
        SharedArrayBuffer,
        Uint8Array,
      })
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
      expect(buffer?.[0]).toBe(0)
    },
  )
})
