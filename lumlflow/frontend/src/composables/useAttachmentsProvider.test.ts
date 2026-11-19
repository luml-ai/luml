import { afterEach, expect, it, vi } from 'vitest'
import { useAttachmentsProvider } from './useAttachmentsProvider'
import { api } from '@/api/client'
import { apiService } from '@/api/api.service'

vi.mock('@/api/api.service', () => ({
  apiService: { getAttachments: vi.fn(), getAttachmentContent: vi.fn() },
}))

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

it.each([null, 1234])(
  'reads ranges using the current length when the listed size is %s',
  async (listed) => {
    const path = 'tables/data + results.parquet'
    const size = 400 * 1024 ** 2
    vi.mocked(apiService.getAttachments).mockResolvedValue([
      { name: 'data + results.parquet', type: 'file', path, size: listed },
    ])
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        new Response(new Uint8Array(1), {
          status: 206,
          headers: { 'Content-Range': `bytes 0-0/${size}` },
        }),
      )
      .mockResolvedValueOnce(
        new Response(new Uint8Array([10, 11]), {
          status: 206,
          headers: { 'Content-Range': `bytes 10-11/${size}` },
        }),
      )
    vi.stubGlobal('fetch', fetch)
    localStorage.setItem('flow-session-token', 'test-token')
    const { init, provider } = useAttachmentsProvider('run')
    await init()
    const data = await provider.value!.getPreviewSource!(path, listed ?? undefined)
    if (typeof data === 'string' || data instanceof Blob) throw new Error('Expected a range reader')
    expect(provider.value!.getTree()[0]?.size).toBe(listed ?? undefined)
    expect(data.byteLength).toBe(size)
    expect(new Uint8Array(await data.slice(10, 12))).toEqual(new Uint8Array([10, 11]))
    const [url, initOptions] = fetch.mock.calls[1]!
    const request = new URL(String(url), window.location.origin)
    expect(request.pathname).toBe('/api/experiments/run/attachments/content')
    expect(request.searchParams.get('file_path')).toBe(path)
    expect(request.searchParams.has('token')).toBe(false)
    const headers = new Headers(initOptions?.headers)
    expect(headers.get('Authorization')).toBe('Bearer test-token')
    expect(headers.get('Range')).toBe('bytes=10-11')
    expect(apiService.getAttachmentContent).not.toHaveBeenCalled()
  },
)

it.each(['song.wav', 'report.pdf', 'run.mp4'])(
  'opens %s over HTTP without service workers',
  async (path) => {
    const size = 300 * 1024 ** 2
    vi.mocked(apiService.getAttachments).mockResolvedValue([
      { name: path, type: 'file', path, size },
    ])
    const ticket = vi
      .spyOn(api, 'post')
      .mockResolvedValue({ data: { expires: 1000, signature: 'file-specific', size } })
    localStorage.setItem('flow-session-token', 'test-token')
    const { init, provider } = useAttachmentsProvider('run')
    await init()
    const source = await provider.value!.getPreviewSource!(path, size)
    const url = new URL(String(source), 'http://lan.example')
    expect(ticket).toHaveBeenCalledWith('/experiments/run/attachments/preview', null, {
      params: { file_path: path },
    })
    expect(url.pathname).toBe('/api/experiments/preview/content')
    expect(url.searchParams.get('signature')).toBe('file-specific')
    expect(url.href).not.toContain('test-token')
    expect(apiService.getAttachmentContent).not.toHaveBeenCalled()
  },
)
