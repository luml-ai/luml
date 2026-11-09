import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useBucketsStore } from '../buckets'

const { getBucketSecretsList } = vi.hoisted(() => ({ getBucketSecretsList: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { bucketSecrets: { getBucketSecretsList } } }))

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
