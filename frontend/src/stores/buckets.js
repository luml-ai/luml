import { api } from '@/lib/api';
import { defineStore } from 'pinia';
import { ref } from 'vue';
import axios from 'axios';
export var BucketValidationErrorCode;
(function (BucketValidationErrorCode) {
    BucketValidationErrorCode["INVALID_STATUS"] = "INVALID_STATUS";
    BucketValidationErrorCode["RANGE_NOT_SUPPORTED"] = "RANGE_NOT_SUPPORTED";
    BucketValidationErrorCode["UNKNOWN"] = "UNKNOWN";
})(BucketValidationErrorCode || (BucketValidationErrorCode = {}));
export class BucketValidationError extends Error {
    code;
    constructor(code) {
        super(code);
        this.code = code;
        this.name = 'BucketValidationError';
    }
    getMessage() {
        switch (this.code) {
            case BucketValidationErrorCode.RANGE_NOT_SUPPORTED:
                return 'Range requests are not supported. Please ensure "Range" is added to "AllowedHeaders" in your bucket\'s CORS configuration.';
            case BucketValidationErrorCode.INVALID_STATUS:
                return 'Bucket validation failed: invalid status';
            case BucketValidationErrorCode.UNKNOWN:
                return 'Bucket validation failed';
            default:
                return 'Bucket validation failed';
        }
    }
}
export const useBucketsStore = defineStore('buckets', () => {
    const buckets = ref([]);
    async function getBuckets(organizationId) {
        buckets.value = await api.bucketSecrets.getBucketSecretsList(organizationId);
    }
    async function createBucket(organizationId, data) {
        const bucket = await api.bucketSecrets.createBucketSecret(organizationId, data);
        buckets.value.push(bucket);
    }
    async function updateBucket(organizationId, bucketId, data) {
        const updatedBucket = await api.bucketSecrets.updateBucketSecret(organizationId, bucketId, data);
        const index = buckets.value.findIndex((bucket) => bucket.id === bucketId);
        if (index !== -1) {
            buckets.value[index] = updatedBucket;
        }
        return updatedBucket;
    }
    async function deleteBucket(organizationId, bucketId) {
        await api.bucketSecrets.deleteBucketSecret(organizationId, bucketId);
        buckets.value = buckets.value.filter((bucket) => bucket.id !== bucketId);
    }
    async function validateRangeSupport(downloadUrl) {
        try {
            const fullResponse = await axios.get(downloadUrl, { validateStatus: () => true });
            if (fullResponse.status !== 200) {
                throw new BucketValidationError(BucketValidationErrorCode.INVALID_STATUS);
            }
            let rangeResponse;
            try {
                rangeResponse = await fetch(downloadUrl, {
                    method: 'GET',
                    headers: { Range: 'bytes=0-10' },
                    mode: 'cors',
                });
            }
            catch (fetchErr) {
                throw new BucketValidationError(BucketValidationErrorCode.RANGE_NOT_SUPPORTED);
            }
            if (rangeResponse.status !== 206 && rangeResponse.status !== 200) {
                throw new BucketValidationError(BucketValidationErrorCode.RANGE_NOT_SUPPORTED);
            }
        }
        catch (err) {
            if (err instanceof BucketValidationError) {
                throw err;
            }
            throw new BucketValidationError(BucketValidationErrorCode.UNKNOWN);
        }
    }
    async function checkBucket(data) {
        const connectionUrls = await api.bucketSecrets.getBucketSecretConnectionUrls(data);
        const text = 'Connection test...';
        const blob = new Blob([text], { type: 'text/plain' });
        const buffer = await blob.arrayBuffer();
        await axios.put(connectionUrls.presigned_url, buffer, {
            headers: { 'Content-Type': 'application/octet-stream', 'x-ms-blob-type': 'BlockBlob' },
        });
        try {
            await validateRangeSupport(connectionUrls.download_url);
        }
        catch (err) {
            await axios.delete(connectionUrls.delete_url).catch(() => { });
            throw err;
        }
        await axios.delete(connectionUrls.delete_url);
    }
    async function checkExistingBucket(organizationId, bucketId, data) {
        const connectionUrls = await api.bucketSecrets.getExistingBucketSecretConnectionUrls(organizationId, bucketId, { ...data, id: bucketId });
        const text = 'Connection test...';
        const blob = new Blob([text], { type: 'text/plain' });
        const buffer = await blob.arrayBuffer();
        await axios.put(connectionUrls.presigned_url, buffer, {
            headers: { 'Content-Type': 'application/octet-stream', 'x-ms-blob-type': 'BlockBlob' },
        });
        try {
            await validateRangeSupport(connectionUrls.download_url);
        }
        catch (err) {
            await axios.delete(connectionUrls.delete_url).catch(() => { });
            throw err;
        }
        await axios.delete(connectionUrls.delete_url);
    }
    return {
        buckets,
        getBuckets,
        createBucket,
        updateBucket,
        deleteBucket,
        checkBucket,
        checkExistingBucket,
    };
});
