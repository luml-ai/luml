export class DeploymentsApi {
    api;
    constructor(api) {
        this.api = api;
    }
    async create(organizationId, orbitId, payload) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments`, payload);
        return responseData;
    }
    async getList(organizationId, orbitId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments`);
        return responseData;
    }
    async getDeployment(organizationId, orbitId, deploymentId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`);
        return responseData;
    }
    async deleteDeployment(organizationId, orbitId, deploymentId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`);
        return responseData;
    }
    async update(organizationId, orbitId, deploymentId, payload) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}`, payload);
        return responseData;
    }
    async forceDeleteDeployment(organizationId, orbitId, deploymentId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/deployments/${deploymentId}/force`);
        return responseData;
    }
}
