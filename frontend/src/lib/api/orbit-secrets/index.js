export class OrbitSecretsApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async getSecrets(organizationId, orbitId) {
        const { data } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/secrets`);
        return data;
    }
    async getSecretById(organizationId, orbitId, secretId) {
        const { data } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`);
        return data;
    }
    async createSecret(organizationId, orbitId, payload) {
        const { data } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/secrets`, payload);
        return data;
    }
    async updateSecret(organizationId, orbitId, payload) {
        const { data } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${payload.id}`, payload);
        return data;
    }
    async deleteSecret(organizationId, orbitId, secretId) {
        const { data } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/secrets/${secretId}`);
        return data;
    }
}
