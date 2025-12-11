import type { BucketSecret, BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
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

export const useBucketsStore = defineStore('buckets', () => {
  const buckets = ref<BucketSecret[]>([])

  async function getBuckets(organizationId: string) {
    buckets.value = await api.bucketSecrets.getBucketSecretsList(organizationId)
  }

  async function createBucket(organizationId: string, data: BucketSecretCreator) {
    const bucket = await api.bucketSecrets.createBucketSecret(organizationId, data)
    buckets.value.push(bucket)
  }

  async function updateBucket(
    organizationId: string,
    bucketId: string,
    data: BucketSecretCreator & { id: string },
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

      let rangeResponse: Response
      try {
        rangeResponse = await fetch(downloadUrl, {
          method: 'GET',
          headers: { Range: 'bytes=0-10' },
          mode: 'cors',
        })
      } catch (fetchErr) {
        throw new BucketValidationError(BucketValidationErrorCode.RANGE_NOT_SUPPORTED)
      }

      if (rangeResponse.status !== 206 && rangeResponse.status !== 200) {
        throw new BucketValidationError(BucketValidationErrorCode.RANGE_NOT_SUPPORTED)
      }
    } catch (err) {
      if (err instanceof BucketValidationError) {
        throw err
      }
      throw new BucketValidationError(BucketValidationErrorCode.UNKNOWN)
    }
  }

  async function checkBucket(data: BucketSecretCreator) {
    const connectionUrls = await api.bucketSecrets.getBucketSecretConnectionUrls(data)
    const text = 'Connection test...'
    const blob = new Blob([text], { type: 'text/plain' })
    const buffer = await blob.arrayBuffer()
    await axios.put(connectionUrls.presigned_url, buffer, {
      headers: { 'Content-Type': 'application/octet-stream' },
    })

    try {
      await validateRangeSupport(connectionUrls.download_url)
    } catch (err) {
      await axios.delete(connectionUrls.delete_url).catch(() => {})
      throw err
    }

    await axios.delete(connectionUrls.delete_url)
  }

  async function checkExistingBucket(
    organizationId: string,
    bucketId: string,
    data: BucketSecretCreator,
  ) {
    const connectionUrls = await api.bucketSecrets.getExistingBucketSecretConnectionUrls(
      organizationId,
      bucketId,
      { ...data, id: bucketId },
    )
    const text = 'Connection test...'
    const blob = new Blob([text], { type: 'text/plain' })
    const buffer = await blob.arrayBuffer()
    await axios.put(connectionUrls.presigned_url, buffer, {
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    try {
      await validateRangeSupport(connectionUrls.download_url)
    } catch (err) {
      await axios.delete(connectionUrls.delete_url).catch(() => {})
      throw err
    }
    await axios.delete(connectionUrls.delete_url)
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
