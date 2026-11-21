import type {
  BucketSecret,
  BucketFormData,
  BucketFormDataWithId,
  BucketConnectionUrls,
} from '@/lib/api/bucket-secrets/interfaces'
import { api } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export enum BucketValidationErrorCode {
  INVALID_STATUS = 'INVALID_STATUS',
  RANGE_NOT_SUPPORTED = 'RANGE_NOT_SUPPORTED',
  UNKNOWN = 'UNKNOWN',
}

export class BucketValidationError extends Error {
  constructor(public code: BucketValidationErrorCode) {
    super(code)
    this.name = 'BucketValidationError'
  }

  getMessage(): string {
    switch (this.code) {
      case BucketValidationErrorCode.RANGE_NOT_SUPPORTED:
        return 'Range requests are not supported. Please ensure "Range" is added to "AllowedHeaders" in your bucket\'s CORS configuration.'
      case BucketValidationErrorCode.INVALID_STATUS:
        return 'Bucket validation failed: invalid status'
      case BucketValidationErrorCode.UNKNOWN:
        return 'Bucket validation failed'
      default:
        return 'Bucket validation failed'
    }
  }
}

/**
 * Written to the bucket and read back by Range. Long enough that a storage ignoring Range and
 * answering with the whole object fails the length check.
 */
const RANGE_TEST_CONTENT = new TextEncoder().encode(
  'LUML connection test: this object checks that the storage answers HTTP Range requests.',
)
// A range from the middle too: some broken implementations only handle a prefix.
const RANGE_CHECKS: [number, number][] = [
  [0, 10],
  [5, 12],
]

/**
 * Status does not tell (some S3 implementations honour Range with 200), so any 2xx passes
 * whose body is exactly the requested bytes of what was written.
 */
async function readsRange(url: string, start: number, end: number): Promise<boolean> {
  let body: Uint8Array
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { Range: `bytes=${start}-${end}` },
      mode: 'cors',
    })
    if (!response.ok) return false
    body = new Uint8Array(await response.arrayBuffer())
  } catch {
    return false
  }
  const expected = RANGE_TEST_CONTENT.subarray(start, end + 1)
  return body.length === expected.length && body.every((byte, index) => byte === expected[index])
}

export const useBucketsStore = defineStore('buckets', () => {
  const buckets = ref<BucketSecret[]>([])
  let bucketsRequestId = 0

  async function getBuckets(organizationId: string) {
    const requestId = ++bucketsRequestId
    try {
      const list = await api.bucketSecrets.getBucketSecretsList(organizationId)
      if (requestId === bucketsRequestId) buckets.value = list
    } catch (e) {
      if (requestId === bucketsRequestId) buckets.value = []
      throw e
    }
  }

  async function createBucket(organizationId: string, data: BucketFormData) {
    const bucket = await api.bucketSecrets.createBucketSecret(organizationId, data)
    buckets.value.push(bucket)
  }

  async function updateBucket(
    organizationId: string,
    bucketId: string,
    data: BucketFormDataWithId,
  ) {
    const updatedBucket = await api.bucketSecrets.updateBucketSecret(organizationId, bucketId, data)
    const index = buckets.value.findIndex((bucket) => bucket.id === bucketId)
    if (index !== -1) {
      buckets.value[index] = updatedBucket
    }
    return updatedBucket
  }

  async function deleteBucket(organizationId: string, bucketId: string) {
    await api.bucketSecrets.deleteBucketSecret(organizationId, bucketId)
    buckets.value = buckets.value.filter((bucket) => bucket.id !== bucketId)
  }

  async function validateRangeSupport(downloadUrl: string): Promise<void> {
    try {
      const fullResponse = await axios.get(downloadUrl, { validateStatus: () => true })
      if (fullResponse.status !== 200) {
        throw new BucketValidationError(BucketValidationErrorCode.INVALID_STATUS)
      }
      for (const [start, end] of RANGE_CHECKS) {
        if (!(await readsRange(downloadUrl, start, end))) {
          throw new BucketValidationError(BucketValidationErrorCode.RANGE_NOT_SUPPORTED)
        }
      }
    } catch (err) {
      if (err instanceof BucketValidationError) {
        throw err
      }
      throw new BucketValidationError(BucketValidationErrorCode.UNKNOWN)
    }
  }

  async function testConnection(connectionUrls: BucketConnectionUrls) {
    await axios.put(connectionUrls.presigned_url, RANGE_TEST_CONTENT.slice().buffer, {
      headers: { 'Content-Type': 'application/octet-stream', 'x-ms-blob-type': 'BlockBlob' },
    })
    try {
      await validateRangeSupport(connectionUrls.download_url)
    } catch (err) {
      await axios.delete(connectionUrls.delete_url).catch(() => {})
      throw err
    }
    await axios.delete(connectionUrls.delete_url)
  }

  async function checkBucket(data: BucketFormData) {
    const connectionUrls = await api.bucketSecrets.getBucketSecretConnectionUrls(data)
    await testConnection(connectionUrls)
  }

  async function checkExistingBucket(
    organizationId: string,
    bucketId: string,
    data: BucketFormData,
  ) {
    const connectionUrls = await api.bucketSecrets.getExistingBucketSecretConnectionUrls(
      organizationId,
      bucketId,
      { ...data, id: bucketId },
    )
    await testConnection(connectionUrls)
  }

  return {
    buckets,
    getBuckets,
    createBucket,
    updateBucket,
    deleteBucket,
    checkBucket,
    checkExistingBucket,
  }
})
