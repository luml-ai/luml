import type { AxiosInstance } from 'axios';
import type { BucketFormData, BucketFormDataWithId } from './interfaces';
export declare class BucketSecretsApi {
    private api;
    constructor(api: AxiosInstance);
    getBucketSecretsList(organizationId: string): Promise<any>;
    getBucketSecret(organizationId: string, secretId: string): Promise<any>;
    createBucketSecret(organizationId: string, data: BucketFormData): Promise<any>;
    updateBucketSecret(organizationId: string, secretId: string, data: BucketFormDataWithId): Promise<any>;
    deleteBucketSecret(organizationId: string, secretId: string): Promise<any>;
    getBucketSecretConnectionUrls(data: BucketFormData): Promise<any>;
    getExistingBucketSecretConnectionUrls(organizationId: string, secretId: string, data: BucketFormDataWithId): Promise<any>;
}
