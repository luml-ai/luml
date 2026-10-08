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
