export class OrbitTracksApi {
    api;
    constructor(api) {
        this.api = api;
    }
    // --- Tracks ---
    async createTrack(organizationId, orbitId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks`, data);
        return responseData;
    }
    async listTracks(organizationId, orbitId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks`);
        return responseData;
    }
    async getTrack(organizationId, orbitId, trackId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`);
        return responseData;
    }
    async updateTrack(organizationId, orbitId, trackId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`, data);
        return responseData;
    }
    async deleteTrack(organizationId, orbitId, trackId) {
        await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}`);
    }
    // --- Entries ---
    async addEntry(organizationId, orbitId, trackId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries`, data);
        return responseData;
    }
    async listEntries(organizationId, orbitId, trackId, params) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries`, { params });
        return responseData;
    }
    async patchEntry(organizationId, orbitId, trackId, entryId, data, force) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries/${entryId}`, data, { params: force ? { force: true } : undefined });
        return responseData;
    }
    async deleteEntry(organizationId, orbitId, trackId, entryId) {
        await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/entries/${entryId}`);
    }
    // --- Artifact track membership ---
    async listArtifactEntries(organizationId, orbitId, artifactId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts/${artifactId}/track-entries`);
        return responseData;
    }
    // --- Stages ---
    async createStage(organizationId, orbitId, trackId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages`, data);
        return responseData;
    }
    async listStages(organizationId, orbitId, trackId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages`);
        return responseData;
    }
    async updateStage(organizationId, orbitId, trackId, stageId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages/${stageId}`, data);
        return responseData;
    }
    async deleteStage(organizationId, orbitId, trackId, stageId, force) {
        await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/tracks/${trackId}/stages/${stageId}`, { params: force ? { force: true } : undefined });
    }
}
