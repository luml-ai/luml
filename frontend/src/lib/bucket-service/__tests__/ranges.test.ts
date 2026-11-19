import { afterEach, expect, it, vi } from 'vitest'
import { ModelDownloader } from '..'

afterEach(() => vi.unstubAllGlobals())

it('renews an expired archive URL and reads only the requested bytes', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 403 }))
    .mockResolvedValueOnce(
      new Response(new Uint8Array([4, 5]), {
        status: 206,
        headers: { 'Content-Range': 'bytes 143-144/300' },
      }),
    )
  vi.stubGlobal('fetch', fetch)
  const renew = vi.fn().mockResolvedValue('https://download.test/renewed')
  const downloader = new ModelDownloader('https://download.test/initial', renew)
  expect(new Uint8Array(await downloader.readRange(143, 145))).toEqual(new Uint8Array([4, 5]))
  expect(renew).toHaveBeenCalledOnce()
  expect(fetch.mock.calls).toEqual([
    ['https://download.test/initial', { headers: { Range: 'bytes=143-144' } }],
    ['https://download.test/renewed', { headers: { Range: 'bytes=143-144' } }],
  ])
})

it.each([
  [200, null],
  [206, 'bytes 0-1/300'],
])(
  'rejects a server response with status %i and range %s before reading the body',
  async (status, range) => {
    const response = new Response('large archive', {
      status,
      headers: range ? { 'Content-Range': range } : {},
    })
    const read = vi.spyOn(response, 'arrayBuffer')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(
      new ModelDownloader('https://download.test/model').readRange(10, 12),
    ).rejects.toThrow('requested byte range')
    expect(read).not.toHaveBeenCalled()
  },
)
