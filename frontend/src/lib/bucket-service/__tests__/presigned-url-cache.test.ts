import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import {
  ModelDownloader,
  PRESIGNED_URL_REUSE_MS,
  PresignedUrlCache,
  RangeLengthMismatchError,
} from '@/lib/bucket-service'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

function issuer() {
  let issued = 0
  return vi.fn(async (id: string) => `https://bucket/${id}?sig=${++issued}`)
}

describe('PresignedUrlCache', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reuses one URL per artifact for 30 minutes', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)

    expect(await cache.get('a')).toBe('https://bucket/a?sig=1')
    vi.advanceTimersByTime(PRESIGNED_URL_REUSE_MS - 1)
    expect(await cache.get('a')).toBe('https://bucket/a?sig=1')
    expect(await cache.get('b')).toBe('https://bucket/b?sig=2')
    expect(fetchUrl).toHaveBeenCalledTimes(2)
  })

  it('renews a URL that is 30 minutes old', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    await cache.get('a')

    vi.advanceTimersByTime(PRESIGNED_URL_REUSE_MS)

    expect(await cache.get('a')).toBe('https://bucket/a?sig=2')
    expect(fetchUrl).toHaveBeenCalledTimes(2)
  })

  it('renews once after a failed request and retries it once', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi
      .fn<(url: string) => Promise<string>>()
      .mockRejectedValueOnce(new Error('403 expired'))
      .mockImplementation(async (url) => `data from ${url}`)

    await expect(cache.withUrl('a', request)).resolves.toBe('data from https://bucket/a?sig=2')
    expect(request.mock.calls.map(([url]) => url)).toEqual([
      'https://bucket/a?sig=1',
      'https://bucket/a?sig=2',
    ])
    expect(fetchUrl).toHaveBeenCalledTimes(2)
    expect(await cache.get('a')).toBe('https://bucket/a?sig=2')
  })

  it('surfaces the error when the retry fails too, without a second renewal', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi.fn(async () => {
      throw new Error('403 expired')
    })

    await expect(cache.withUrl('a', request)).rejects.toThrow('403 expired')
    expect(request).toHaveBeenCalledTimes(2)
    expect(fetchUrl).toHaveBeenCalledTimes(2)
  })

  it('does not renew or retry an aborted request', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi.fn(async () => {
      throw new DOMException('Aborted', 'AbortError')
    })

    await expect(cache.withUrl('a', request)).rejects.toMatchObject({ name: 'AbortError' })
    expect(request).toHaveBeenCalledOnce()
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it('shares one in-flight request between concurrent callers', async () => {
    let release!: (url: string) => void
    const fetchUrl = vi.fn(() => new Promise<string>((resolve) => (release = resolve)))
    const cache = new PresignedUrlCache(fetchUrl)

    const urls = Promise.all([cache.get('a'), cache.get('a'), cache.renew('a', 'stale')])
    release('https://bucket/a?sig=1')

    await expect(urls).resolves.toEqual(Array(3).fill('https://bucket/a?sig=1'))
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it('renews once for concurrent failures of the same URL', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const failed = await cache.get('a')

    const renewed = await Promise.all([cache.renew('a', failed), cache.renew('a', failed)])
    const late = await cache.renew('a', failed)

    expect(renewed).toEqual(['https://bucket/a?sig=2', 'https://bucket/a?sig=2'])
    expect(late).toBe('https://bucket/a?sig=2')
    expect(fetchUrl).toHaveBeenCalledTimes(2)
  })

  it('lets a failed URL request be retried by the next caller', async () => {
    const fetchUrl = vi
      .fn<(id: string) => Promise<string>>()
      .mockRejectedValueOnce(new Error('backend down'))
      .mockResolvedValue('https://bucket/a?sig=1')
    const cache = new PresignedUrlCache(fetchUrl)

    await expect(cache.get('a')).rejects.toThrow('backend down')
    await expect(cache.get('a')).resolves.toBe('https://bucket/a?sig=1')
  })
})

describe('ModelDownloader', () => {
  it('reads a member with a Range header through the cached URL and retries once', async () => {
    const cache = new PresignedUrlCache(issuer())
    vi.mocked(axios.get)
      .mockRejectedValueOnce(new Error('403'))
      .mockResolvedValueOnce({ data: new ArrayBuffer(4) })
    const downloader = new ModelDownloader(cache.source('a'))

    const data = await downloader.getFileFromBucket({ 'exp.db.zip': [512, 4] }, 'exp.db.zip', true)

    expect(data).toBeInstanceOf(ArrayBuffer)
    expect(vi.mocked(axios.get).mock.calls).toEqual([
      ['https://bucket/a?sig=1', expect.objectContaining({ headers: { Range: 'bytes=512-515' } })],
      ['https://bucket/a?sig=2', expect.objectContaining({ headers: { Range: 'bytes=512-515' } })],
    ])
  })
})

describe('PresignedUrlCache with locations that carry headers', () => {
  const url = 'https://workspace.test/api/2.0/fs/files/a.tar'
  function tokenIssuer() {
    let issued = 0
    return vi.fn(async () => ({ url, headers: { Authorization: `Bearer t${++issued}` } }))
  }

  it('renews a token for the same URL once and shares it with a late failure', async () => {
    const fetchLocation = tokenIssuer()
    const cache = new PresignedUrlCache(fetchLocation)
    const failed = await cache.getLocation('a')

    const renewed = await cache.renewLocation('a', failed)
    const late = await cache.renewLocation('a', { url, headers: { Authorization: 'Bearer t1' } })

    expect(renewed).toEqual({ url, headers: { Authorization: 'Bearer t2' } })
    expect(late).toBe(renewed)
    expect(fetchLocation).toHaveBeenCalledTimes(2)
    expect(await cache.get('a')).toBe(url)
  })

  it('hands a bare issued URL back unchanged and retries with the renewed one', async () => {
    const cache = new PresignedUrlCache(issuer())
    expect(await cache.getLocation('a')).toBe('https://bucket/a?sig=1')

    const request = vi
      .fn<(location: { url: string }) => Promise<string>>()
      .mockRejectedValueOnce(new Error('401'))
      .mockImplementation(async (location) => location.url)

    await expect(cache.withLocation('a', request)).resolves.toBe('https://bucket/a?sig=2')
  })
})

describe('ModelDownloader range checks', () => {
  beforeEach(() => vi.mocked(axios.get).mockReset())

  it('sends the location headers and credentials mode with the Range header', async () => {
    const location = {
      url: 'https://proxy.test/a',
      headers: { Authorization: 'Bearer t1' },
      credentials: 'include' as const,
    }
    const cache = new PresignedUrlCache(async () => location)
    vi.mocked(axios.get).mockResolvedValue({ data: new ArrayBuffer(4) })

    await new ModelDownloader(cache.source('a')).getFileFromBucket({ f: [0, 4] }, 'f', true)

    expect(vi.mocked(axios.get).mock.calls[0]).toEqual([
      'https://proxy.test/a',
      expect.objectContaining({
        headers: { Authorization: 'Bearer t1', Range: 'bytes=0-3' },
        withCredentials: true,
      }),
    ])
  })

  it('fails with a typed error, without renewing, when the body has another length', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    vi.mocked(axios.get).mockResolvedValue({ data: new ArrayBuffer(1000) })
    const downloader = new ModelDownloader(cache.source('a'))

    const read = downloader.getFileFromBucket({ 'index.json': [512, 10] }, 'index.json')

    await expect(read).rejects.toBeInstanceOf(RangeLengthMismatchError)
    await expect(read).rejects.toMatchObject({ expected: 10, received: 1000 })
    expect(axios.get).toHaveBeenCalledOnce()
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it('parses a JSON member and hands text that is not JSON over as text', async () => {
    const cache = new PresignedUrlCache(issuer())
    const downloader = new ModelDownloader(cache.source('a'))
    const body = (text: string) => ({ data: new TextEncoder().encode(text).buffer })
    vi.mocked(axios.get)
      .mockResolvedValueOnce(body('{"a":[0,1]}'))
      .mockResolvedValueOnce(body('not json!!!'))

    expect(await downloader.getFileFromBucket({ f: [0, 11] }, 'f')).toEqual({ a: [0, 1] })
    expect(await downloader.getFileFromBucket({ f: [0, 11] }, 'f')).toBe('not json!!!')
  })
})
