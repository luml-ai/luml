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

  async function checkBucket(data: BucketSecretCreator) {
    const connectionUrls = await dataforceApi.bucketSecrets.getBucketSecretConnectionUrls(data)
    const text = 'Connection test...'
    const blob = new Blob([text], { type: 'text/plain' })
    const buffer = await blob.arrayBuffer()
    await axios.put(connectionUrls.presigned_url, buffer, {
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    await axios.get(connectionUrls.download_url)
    await axios.delete(connectionUrls.delete_url)
  }

  return {
    buckets,
    getBuckets,
    createBucket,
    updateBucket,
    deleteBucket,
    checkBucket,
  }
})
