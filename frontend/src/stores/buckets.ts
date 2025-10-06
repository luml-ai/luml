import type { BucketSecret, BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { dataforceApi } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useBucketsStore = defineStore('buckets', () => {
  const buckets = ref<BucketSecret[]>([])

  async function getBuckets(organizationId: number) {
    buckets.value = await dataforceApi.bucketSecrets.getBucketSecretsList(organizationId)
  }

  async function createBucket(organizationId: number, data: BucketSecretCreator) {
    const bucket = await dataforceApi.bucketSecrets.createBucketSecret(organizationId, data)
    buckets.value.push(bucket)
  }

  async function updateBucket(
    organizationId: number,
    bucketId: number,
    data: BucketSecretCreator & { id: number },
  ) {
    const updatedBucket = await dataforceApi.bucketSecrets.updateBucketSecret(
      organizationId,
      bucketId,
      data,
    )
    const index = buckets.value.findIndex((bucket) => bucket.id === bucketId)
    if (index !== -1) {
      buckets.value[index] = updatedBucket
    }
    return updatedBucket
  }

  async function deleteBucket(organizationId: number, bucketId: number) {
    await dataforceApi.bucketSecrets.deleteBucketSecret(organizationId, bucketId)
    buckets.value = buckets.value.filter((bucket) => bucket.id !== bucketId)
  }

  async function validateRangeSupport(downloadUrl: string): Promise<void> {
    try {
      const fullResponse = await axios.get(downloadUrl, { validateStatus: () => true })
      if (fullResponse.status !== 200) {
        throw new Error('Bucket validation failed: invalid status')
      }

      let rangeResponse: Response
      try {
        rangeResponse = await fetch(downloadUrl, {
          method: 'GET',
          headers: { Range: 'bytes=0-10,20-30' },
          mode: 'cors',
        })
      } catch (fetchErr) {
        throw new Error(
          'Range requests are not supported.  Please ensure "Range" is added to "AllowedHeaders" in your bucket\'s CORS configuration',
        )
      }

      if (rangeResponse.status !== 206) {
        throw new Error(
          'Range requests are not supported. Please ensure "Range" is added to "AllowedHeaders" in your bucket\'s CORS configuration.',
        )
      }

    } catch (err) {
      throw err instanceof Error ? err : new Error('Bucket validation failed')
    }
  }

  async function checkBucket(data: BucketSecretCreator) {
    const connectionUrls = await dataforceApi.bucketSecrets.getBucketSecretConnectionUrls(data)
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
    organizationId: number,
    bucketId: number,
    data: BucketSecretCreator,
  ) {
    const connectionUrls = await dataforceApi.bucketSecrets.getExistingBucketSecretConnectionUrls(
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
