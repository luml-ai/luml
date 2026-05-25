export class SatellitesApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async create(organizationId, orbitId, payload) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites`, payload);
        return responseData;
    }
    async update(organizationId, orbitId, satelliteId, payload) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`, payload);
        return responseData;
    }
    async getList(organizationId, orbitId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites`);
        return responseData;
    }
    async getItem(organizationId, orbitId, satelliteId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`);
        return responseData;
    }
    async delete(organizationId, orbitId, satelliteId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}`);
        return responseData;
    }
    async regenerateApiKye(organizationId, orbitId, satelliteId) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/satellites/${satelliteId}/api-key`);
        return responseData;
    }
}
