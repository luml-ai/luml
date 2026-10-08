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
