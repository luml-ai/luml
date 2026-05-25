export class ApiKeysApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async createApiKey() {
        const { data: responseData } = await this.api.post(`/v1/users/me/api-keys`);
        return responseData;
    }
    async deleteApiKey() {
        await this.api.delete(`/v1/users/me/api-keys`);
    }
}
