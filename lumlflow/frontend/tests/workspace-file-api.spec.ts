import { afterEach, describe, expect, it, vi } from 'vitest'
import { FlowStream } from '@/api/streams/flow'
import { api } from '@/api/client'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('Workspace file transport', () => {
  it('encodes a local preview URL and preserves special characters in the absolute path', () => {
    const path = '/project/a #1 & 2?.csv'
    expect(() => workspaceApi.fileUrl(path)).toThrow()
    localStorage.setItem('lumlflow.flow.token', 'test key')
    const url = new URL(workspaceApi.fileUrl(path), location.origin)
    expect(url.origin).toBe(location.origin)
    expect(url.pathname).toBe('/api/flow/file')
    expect(Object.fromEntries(url.searchParams)).toEqual({ path, token: 'test key' })
  })

  it('uses the configured backend origin and API prefix for bytes and watcher sockets', () => {
    const originalBase = api.defaults.baseURL
    const connect = vi.fn()
    vi.stubGlobal(
      'WebSocket',
      class {
        constructor(url: string) {
          connect(url)
        }
      },
    )
    try {
      api.defaults.baseURL = 'https://daemon.example.test/custom/api/'
      localStorage.setItem('lumlflow.flow.token', 'local')
      const bytes = new URL(workspaceApi.fileUrl('/project/plot.png'))
      expect(bytes.origin + bytes.pathname).toBe('https://daemon.example.test/custom/api/flow/file')
      new FlowStream({ token: 'local' }).connect()
      expect(connect).toHaveBeenCalledWith(
        'wss://daemon.example.test/custom/api/flow/stream?token=local',
      )
    } finally {
      api.defaults.baseURL = originalBase
      vi.unstubAllGlobals()
    }
  })

  it('passes both full-precision version fields when overwriting an edit', async () => {
    localStorage.setItem('lumlflow.flow.token', 'test')
    const post = vi.spyOn(api, 'post').mockResolvedValue({ status: 200, data: { result: {} } })
    await workspaceApi.writeText('/p/notes.md', 'edited', '1734567890123456789', 'original', true)
    expect(post).toHaveBeenCalledWith(
      'flow/rpc',
      {
        method: 'file.write_text',
        params: {
          path: '/p/notes.md',
          text: 'edited',
          mtime_ns: '1734567890123456789',
          revision: 'original',
          force: true,
        },
      },
      expect.objectContaining({ headers: { 'x-lumlflow-token': 'test' } }),
    )
  })

  it('surfaces the notebook names from the daemon and sends explicit close consent on retry', async () => {
    localStorage.setItem('lumlflow.flow.token', 'test')
    const flows = [
      { name: 'analysis', path: '/p/team/analysis.flow', session_id: 'analysis-session' },
    ]
    const post = vi
      .spyOn(api, 'post')
      .mockResolvedValueOnce({
        status: 409,
        data: { error: { message: 'close first', kind: 'FlowOpen', flows } },
      })
      .mockResolvedValueOnce({ status: 200, data: { result: { path: '/p/team' } } })
    await expect(workspaceApi.deleteFile('/p/team')).rejects.toMatchObject({
      kind: 'FlowOpen',
      details: { flows },
    })
    await workspaceApi.deleteFile('/p/team', ['analysis-session'])
    expect(post.mock.calls.map(([, body]) => body)).toEqual(
      [false, ['analysis-session']].map((close) => ({
        method: 'file.delete',
        params: { path: '/p/team', close_open: close },
      })),
    )
  })
})
