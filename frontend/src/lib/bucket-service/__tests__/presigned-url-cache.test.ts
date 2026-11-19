import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import {
  ModelDownloader,
  PRESIGNED_URL_MIN_RENEW_AGE_MS,
  PRESIGNED_URL_REUSE_MS,
  PresignedUrlCache,
  RangeLengthMismatchError,
  toDownloadLocation,
} from '@/lib/bucket-service'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))

function issuer() {
  let issued = 0
  return vi.fn(async (id: string) => `https://bucket/${id}?sig=${++issued}`)
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

/** Issues the first URL and lets it age past the minimum, as a URL that really expired. */
async function issuedLongAgo(cache: PresignedUrlCache, artifactId = 'a') {
  const ref = await cache.getLocation(artifactId)
  vi.advanceTimersByTime(PRESIGNED_URL_MIN_RENEW_AGE_MS)
  return ref
}

describe('PresignedUrlCache', () => {
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
    await issuedLongAgo(cache)
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
    await issuedLongAgo(cache)
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
    const failed = toDownloadLocation(await issuedLongAgo(cache)).url

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

  it('hands back a URL younger than 30 seconds instead of asking the backend', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const failed = await cache.get('a')

    vi.advanceTimersByTime(PRESIGNED_URL_MIN_RENEW_AGE_MS - 1)
    expect(await cache.renew('a', failed)).toBe(failed)
    expect(await cache.renewLocation('a', failed)).toBe(failed)
    expect(fetchUrl).toHaveBeenCalledOnce()

    vi.advanceTimersByTime(1)
    expect(await cache.renew('a', failed)).toBe('https://bucket/a?sig=2')
    expect(fetchUrl).toHaveBeenCalledTimes(2)
  })

  it('costs one renewal when storage rejects every URL', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    await issuedLongAgo(cache)
    const request = vi.fn(async () => {
      throw new Error('403 signature does not match')
    })

    for (let read = 0; read < 5; read++) {
      await expect(cache.withUrl('a', request)).rejects.toThrow('403 signature')
    }

    expect(fetchUrl).toHaveBeenCalledTimes(2)
    expect(request).toHaveBeenCalledTimes(2 + 4)
  })

  it('surfaces the error without a retry when the URL just issued fails', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi.fn(async () => {
      throw new Error('403')
    })

    await expect(cache.withUrl('a', request)).rejects.toThrow('403')
    expect(request).toHaveBeenCalledOnce()
    expect(fetchUrl).toHaveBeenCalledOnce()
  })
  it.each([
    ['a dropped connection', Object.assign(new Error('Network Error'), { isAxiosError: true })],
    ['a failed fetch', new TypeError('Failed to fetch')],
    ['a 500', { isAxiosError: true, response: { status: 500 } }],
    ['a 503', { isAxiosError: true, response: { status: 503 } }],
    ['a 429', { isAxiosError: true, response: { status: 429 } }],
  ])('retries the URL just issued once, without a renewal, after %s', async (_label, failure) => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi
      .fn<(url: string) => Promise<string>>()
      .mockRejectedValueOnce(failure)
      .mockImplementation(async (url) => `data from ${url}`)

    await expect(cache.withUrl('a', request)).resolves.toBe('data from https://bucket/a?sig=1')
    expect(request).toHaveBeenCalledTimes(2)
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it('surfaces a transient failure of the URL just issued after one retry', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const failure = { isAxiosError: true, response: { status: 500 } }
    const request = vi.fn(async () => {
      throw failure
    })

    await expect(cache.withUrl('a', request)).rejects.toBe(failure)
    expect(request).toHaveBeenCalledTimes(2)
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it.each([403, 404])('does not send the URL just issued again after a %s', async (status) => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const request = vi.fn(async () => {
      throw { isAxiosError: true, response: { status } }
    })

    await expect(cache.withUrl('a', request)).rejects.toMatchObject({ response: { status } })
    expect(request).toHaveBeenCalledOnce()
    expect(fetchUrl).toHaveBeenCalledOnce()
  })
})

describe('ModelDownloader', () => {
  it('reads a member with a Range header through the cached URL and retries once', async () => {
    const cache = new PresignedUrlCache(issuer())
    await issuedLongAgo(cache)
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
    const failed = await issuedLongAgo(cache)

    const renewed = await cache.renewLocation('a', failed)
    const late = await cache.renewLocation('a', { url, headers: { Authorization: 'Bearer t1' } })

    expect(renewed).toEqual({ url, headers: { Authorization: 'Bearer t2' } })
    expect(late).toBe(renewed)
    expect(fetchLocation).toHaveBeenCalledTimes(2)
    expect(await cache.get('a')).toBe(url)
  })

  it('hands a bare issued URL back unchanged and retries with the renewed one', async () => {
    const cache = new PresignedUrlCache(issuer())
    expect(await issuedLongAgo(cache)).toBe('https://bucket/a?sig=1')

    const request = vi
      .fn<(location: { url: string }) => Promise<string>>()
      .mockRejectedValueOnce(new Error('401'))
      .mockImplementation(async (location) => location.url)

    await expect(cache.withLocation('a', request)).resolves.toBe('https://bucket/a?sig=2')
  })
})

describe('ModelDownloader range checks', () => {
  // A block body: a function returned from beforeEach runs as a teardown, and this one is the mock.
  beforeEach(() => {
    vi.mocked(axios.get).mockReset()
  })

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

  /** Answers with `size` bytes after one progress event, unless the reader aborts on it. */
  function answerWithProgress(size: number, wasAborted: { value: boolean }) {
    vi.mocked(axios.get).mockImplementation(async (_url, config) => {
      config?.onDownloadProgress?.({ loaded: Math.min(size, 16_384), total: size, bytes: 0 })
      wasAborted.value = (config?.signal as AbortSignal | undefined)?.aborted ?? false
      if (wasAborted.value) throw Object.assign(new Error('canceled'), { name: 'CanceledError' })
      return { data: new ArrayBuffer(size) }
    })
  }

  it('stops a body longer than the range at its first progress and fails with a typed error', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const wasAborted = { value: false }
    answerWithProgress(1_000_000, wasAborted)

    const read = new ModelDownloader(cache.source('a')).getFileFromBucket({ f: [512, 2] }, 'f')

    await expect(read).rejects.toBeInstanceOf(RangeLengthMismatchError)
    await expect(read).rejects.toMatchObject({ expected: 2, received: 1_000_000 })
    await expect(read).rejects.not.toHaveProperty('message', expect.stringContaining('sig='))
    expect(wasAborted.value).toBe(true)
    expect(axios.get).toHaveBeenCalledOnce()
    expect(fetchUrl).toHaveBeenCalledOnce()
  })

  it('reads a range answered with exactly its length without stopping it', async () => {
    const cache = new PresignedUrlCache(issuer())
    const wasAborted = { value: false }
    answerWithProgress(4, wasAborted)

    const data = await new ModelDownloader(cache.source('a')).getFileFromBucket(
      { f: [512, 4] },
      'f',
      true,
    )

    expect(data).toEqual(new ArrayBuffer(4))
    expect(wasAborted.value).toBe(false)
  })

  it('passes a caller abort through without renewing the URL', async () => {
    const fetchUrl = issuer()
    const cache = new PresignedUrlCache(fetchUrl)
    const caller = new AbortController()
    caller.abort()
    vi.mocked(axios.get).mockImplementation(async (_url, config) => {
      if ((config?.signal as AbortSignal | undefined)?.aborted) {
        throw Object.assign(new Error('canceled'), { name: 'CanceledError' })
      }
      return { data: new ArrayBuffer(4) }
    })

    const read = new ModelDownloader(cache.source('a')).getFileFromBucket(
      { f: [0, 4] },
      'f',
      true,
      0,
      caller.signal,
    )

    await expect(read).rejects.toHaveProperty('name', 'CanceledError')
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
