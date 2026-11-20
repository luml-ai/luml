import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { BucketValidationError, BucketValidationErrorCode, useBucketsStore } from '../buckets'

const { getBucketSecretsList, getConnectionUrls, getExistingConnectionUrls } = vi.hoisted(() => ({
  getBucketSecretsList: vi.fn(),
  getConnectionUrls: vi.fn(),
  getExistingConnectionUrls: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    bucketSecrets: {
      getBucketSecretsList,
      getBucketSecretConnectionUrls: getConnectionUrls,
      getExistingBucketSecretConnectionUrls: getExistingConnectionUrls,
    },
  },
}))

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

const bucket = { id: 'bucket-1', bucket_name: 'first' }
const otherBucket = { id: 'bucket-2', bucket_name: 'second' }

describe('getBuckets', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('clears the previous list and rethrows when the request fails', async () => {
    const store = useBucketsStore()
    getBucketSecretsList.mockResolvedValueOnce([bucket])
    await store.getBuckets('org')
    expect(store.buckets).toEqual([bucket])

    const error = new Error('Buckets unavailable')
    getBucketSecretsList.mockRejectedValueOnce(error)
    await expect(store.getBuckets('org')).rejects.toBe(error)
    expect(store.buckets).toEqual([])
  })

  it('keeps the newer list when an older request fails later', async () => {
    const store = useBucketsStore()
    let rejectOlder!: (error: Error) => void
    getBucketSecretsList.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectOlder = reject
      }),
    )
    const older = store.getBuckets('org')
    getBucketSecretsList.mockResolvedValueOnce([otherBucket])
    await store.getBuckets('other-org')

    rejectOlder(new Error('Buckets unavailable'))
    await expect(older).rejects.toThrow('Buckets unavailable')
    expect(store.buckets).toEqual([otherBucket])
  })

  it('ignores an older response that arrives after a newer one', async () => {
    const store = useBucketsStore()
    let resolveOlder!: (list: unknown[]) => void
    getBucketSecretsList.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOlder = resolve
      }),
    )
    const older = store.getBuckets('org')
    getBucketSecretsList.mockResolvedValueOnce([otherBucket])
    await store.getBuckets('other-org')

    resolveOlder([bucket])
    await older
    expect(store.buckets).toEqual([otherBucket])
  })
})

describe('bucket connection check', () => {
  const urls = {
    presigned_url: 'https://bucket/test?put',
    download_url: 'https://bucket/test?get',
    delete_url: 'https://bucket/test?delete',
  }
  let written: Uint8Array
  let rangesAsked: string[]

  type RangeAnswer = (written: Uint8Array, start: number, end: number) => Response

  function storage(answer: RangeAnswer) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        const range = new Headers(init.headers).get('Range') ?? ''
        rangesAsked.push(range)
        const match = /^bytes=(\d+)-(\d+)$/.exec(range) ?? []
        return answer(written, Number(match[1]), Number(match[2]))
      }),
    )
  }

  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    rangesAsked = []
    getConnectionUrls.mockResolvedValue(urls)
    getExistingConnectionUrls.mockResolvedValue(urls)
    vi.mocked(axios.put).mockImplementation(async (_url, data) => {
      written = new Uint8Array(data as ArrayBuffer)
      return { status: 200 }
    })
    vi.mocked(axios.get).mockResolvedValue({ status: 200 })
    vi.mocked(axios.delete).mockResolvedValue({ status: 204 })
  })

  afterEach(() => vi.unstubAllGlobals())

  const partial =
    (status: number): RangeAnswer =>
    (bytes, start, end) =>
      new Response(bytes.slice(start, end + 1), { status })

  it('writes content long enough that a whole-object answer cannot pass for 11 bytes', async () => {
    storage(partial(206))
    await useBucketsStore().checkBucket({} as never)
    expect(written.length).toBeGreaterThan(64)
  })

  it.each([
    ['206 with the requested bytes', partial(206)],
    ['200 with the requested bytes', partial(200)],
  ])(
    'passes a storage answering %s, reading a prefix and a middle range',
    async (_label, answer) => {
      storage(answer)

      await expect(useBucketsStore().checkBucket({} as never)).resolves.toBeUndefined()

      expect(rangesAsked).toEqual(['bytes=0-10', 'bytes=5-12'])
      expect(axios.delete).toHaveBeenCalledExactlyOnceWith(urls.delete_url)
    },
  )

  it.each<[string, RangeAnswer]>([
    ['200 with the whole object', (bytes) => new Response(bytes.slice(), { status: 200 })],
    [
      '206 with other bytes of the right length',
      (bytes, start, end) => new Response(bytes.slice(start + 1, end + 2), { status: 206 }),
    ],
    [
      '206 that only handles a prefix',
      (bytes, start, end) => new Response(bytes.slice(0, end - start + 1), { status: 206 }),
    ],
    ['403', () => new Response('denied', { status: 403 })],
    [
      'a CORS failure',
      () => {
        throw new TypeError('Failed to fetch')
      },
    ],
  ])('fails a storage answering %s and removes the test object', async (_label, answer) => {
    storage(answer)

    const check = useBucketsStore().checkBucket({} as never)

    await expect(check).rejects.toBeInstanceOf(BucketValidationError)
    await expect(check).rejects.toMatchObject({
      code: BucketValidationErrorCode.RANGE_NOT_SUPPORTED,
    })
    expect(axios.delete).toHaveBeenCalledExactlyOnceWith(urls.delete_url)
  })

  it('checks an existing bucket the same way', async () => {
    storage((bytes) => new Response(bytes.slice(), { status: 200 }))

    await expect(
      useBucketsStore().checkExistingBucket('org', 'bucket-1', {} as never),
    ).rejects.toMatchObject({ code: BucketValidationErrorCode.RANGE_NOT_SUPPORTED })
    expect(getExistingConnectionUrls).toHaveBeenCalledWith('org', 'bucket-1', { id: 'bucket-1' })
    expect(axios.delete).toHaveBeenCalledExactlyOnceWith(urls.delete_url)
  })
})
