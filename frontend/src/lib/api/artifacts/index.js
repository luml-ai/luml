import qs from 'qs';
export class ArtifactsApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async create(organizationId, orbitId, collectionId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`, data);
        return responseData;
    }
    async getList(organizationId, orbitId, collectionId, params, signal) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts`, {
            params,
            signal,
            paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
        });
        return responseData;
    }
    async update(organizationId, orbitId, collectionId, artifactId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`, data);
        return responseData;
    }
    async getDownloadUrl(organizationId, orbitId, collectionId, artifactId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/download-url`);
        return responseData;
    }
    async getDeleteUrl(organizationId, orbitId, collectionId, artifactId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/delete-url`);
        return responseData;
    }
    async confirmDelete(organizationId, orbitId, collectionId, artifactId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`);
        return responseData;
    }
    async forceDelete(organizationId, orbitId, collectionId, artifactId) {
        return this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}/force`);
    }
    async getById(organizationId, orbitId, collectionId, artifactId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/artifacts/${artifactId}`);
        return responseData;
    }
}
