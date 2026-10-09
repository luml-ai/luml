import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it, vi } from 'vitest'

const source = readFileSync('public/webworker.js', 'utf8')

describe('Pyodide worker initialization failures', () => {
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
