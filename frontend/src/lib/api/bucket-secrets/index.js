export class BucketSecretsApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async getBucketSecretsList(organizationId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/bucket-secrets`);
        return responseData;
    }
    async getBucketSecret(organizationId, secretId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/bucket-secrets/${secretId}`);
        return responseData;
    }
    async createBucketSecret(organizationId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/bucket-secrets`, data);
        return responseData;
    }
    async updateBucketSecret(organizationId, secretId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/bucket-secrets/${secretId}`, data);
        return responseData;
    }
    async deleteBucketSecret(organizationId, secretId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/bucket-secrets/${secretId}`);
        return responseData;
    }
    async getBucketSecretConnectionUrls(data) {
        const { data: responseData } = await this.api.post(`/v1/bucket-secrets/urls`, data);
        return responseData;
    }
    async getExistingBucketSecretConnectionUrls(organizationId, secretId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/bucket-secrets/${secretId}/urls`, data);
        return responseData;
    }
}
