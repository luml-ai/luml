import qs from 'qs';
export class OrbitCollectionsApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async getCollectionsList(organizationId, orbitId, params) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections`, { params, paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }) });
        return responseData;
    }
    async createCollection(organizationId, orbitId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections`, data);
        return responseData;
    }
    async updateCollection(organizationId, orbitId, collectionId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`, data);
        return responseData;
    }
    async deleteCollection(organizationId, orbitId, collectionId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`);
        return responseData;
    }
    async getCollection(organizationId, orbitId, collectionId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}`);
        return responseData;
    }
}
