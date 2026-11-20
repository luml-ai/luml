import { afterEach, expect, it, vi } from 'vitest'
import { ModelDownloader, PresignedUrlCache, type DownloadRef } from '..'

function downloadUrls(...refs: DownloadRef[]) {
  const issue = vi.fn(async () => refs.shift()!)
  return { issue, source: new PresignedUrlCache(issue, undefined, 0).source('model') }
}

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
  const urls = downloadUrls('https://download.test/initial', 'https://download.test/renewed')
  const downloader = new ModelDownloader(urls.source)
  expect(new Uint8Array(await downloader.readRange(143, 145))).toEqual(new Uint8Array([4, 5]))
  expect(urls.issue).toHaveBeenCalledTimes(2)
  expect(fetch.mock.calls).toEqual([
    ['https://download.test/initial', { headers: { Range: 'bytes=143-144' } }],
    ['https://download.test/renewed', { headers: { Range: 'bytes=143-144' } }],
  ])
})

it('sends the headers and credentials mode of the download location', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(new Uint8Array([7]), { status: 206 }))
  vi.stubGlobal('fetch', fetch)
  const location = {
    url: 'https://workspace.test/api/2.0/fs/files/model.tar',
    headers: { Authorization: 'Bearer token' },
    credentials: 'omit' as const,
  }
  const downloader = new ModelDownloader(downloadUrls(location).source)
  expect(new Uint8Array(await downloader.readRange(5, 6))).toEqual(new Uint8Array([7]))
  expect(fetch.mock.calls).toEqual([
    [
      location.url,
      { headers: { Authorization: 'Bearer token', Range: 'bytes=5-5' }, credentials: 'omit' },
    ],
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
      new ModelDownloader(downloadUrls('https://download.test/model').source).readRange(10, 12),
    ).rejects.toThrow('requested byte range')
    expect(read).not.toHaveBeenCalled()
  },
)
