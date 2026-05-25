import axios from 'axios';
import { installInterceptors } from './api.interceptors';
import { BucketSecretsApi } from './bucket-secrets';
import { OrbitCollectionsApi } from './orbit-collections';
import { ArtifactsApi } from './artifacts';
import { ApiKeysApi } from './api-keys';
import { SatellitesApi } from './satellites';
import { OrbitSecretsApi } from './orbit-secrets';
import { DeploymentsApi } from './deployments';
import { PrismaApi } from './prisma';
import { OrbitTracksApi } from './orbit-tracks';
export class ApiClass {
    api;
    bucketSecrets;
    orbitCollections;
    artifacts;
    apiKeys;
    satellites;
    orbitSecrets;
    deployments;
    dataAgent;
    orbitTracks;
    constructor() {
        this.api = axios.create({
            baseURL: import.meta.env.VITE_API_URL,
            timeout: 10000,
            withCredentials: true,
        });
        installInterceptors(this.api);
        this.bucketSecrets = new BucketSecretsApi(this.api);
        this.orbitCollections = new OrbitCollectionsApi(this.api);
        this.artifacts = new ArtifactsApi(this.api);
        this.apiKeys = new ApiKeysApi(this.api);
        this.satellites = new SatellitesApi(this.api);
        this.orbitSecrets = new OrbitSecretsApi(this.api);
        this.deployments = new DeploymentsApi(this.api);
        this.dataAgent = new PrismaApi();
        this.orbitTracks = new OrbitTracksApi(this.api);
    }
    async signUp(data) {
        const { data: responseData } = await this.api.post('/v1/auth/signup', data, {
            skipInterceptors: true,
        });
        return responseData;
    }
    async signIn(data) {
        const { data: responseData } = await this.api.post('/v1/auth/signin', data, {
            skipInterceptors: true,
        });
        return responseData;
    }
    async googleLogin(params) {
        const { data } = await this.api.get('/v1/auth/google/callback', {
            skipInterceptors: true,
            params,
        });
        return data;
    }
    async microsoftLogin(params) {
        const { data } = await this.api.get('/v1/auth/microsoft/callback', {
            skipInterceptors: true,
            params,
        });
        return data;
    }
    async refreshToken() {
        const { data: responseData } = await this.api.post('/v1/auth/refresh', {}, {
            skipInterceptors: true,
        });
        return responseData;
    }
    async forgotPassword(data) {
        const { data: responseData } = await this.api.post('/v1/auth/forgot-password', data, {
            skipInterceptors: true,
        });
        return responseData;
    }
    async getMe() {
        const { data: responseData } = await this.api.get('/v1/auth/users/me');
        return responseData;
    }
    async updateUser(data) {
        const { data: responseData } = await this.api.patch('/v1/auth/users/me', data);
        return responseData;
    }
    async deleteUser() {
        const { data: responseData } = await this.api.delete('/v1/auth/users/me');
        return responseData;
    }
    async logout() {
        const { data: responseData } = await this.api.post('/v1/auth/logout', {});
        return responseData;
    }
    async resetPassword(data) {
        await this.api.post('/v1/auth/reset-password', data);
    }
    async sendEmail(data) {
        await this.api.post('/v1/stats/email-send', data, {
            skipInterceptors: true,
        });
    }
    async getInvitations() {
        const { data: responseData } = await this.api.get('/v1/users/me/invitations');
        return responseData;
    }
    async createInvite(organizationId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/invitations`, data);
        return responseData;
    }
    async acceptInvitation(inviteId) {
        await this.api.post(`/v1/users/me/invitations/${inviteId}/accept`);
    }
    async rejectInvitation(inviteId) {
        await this.api.post(`/v1/users/me/invitations/${inviteId}/reject`);
    }
    async cancelInvitation(organizationId, inviteId) {
        await this.api.delete(`/v1/organizations/${organizationId}/invitations/${inviteId}`);
    }
    async getOrganizations() {
        const { data: responseData } = await this.api.get('/v1/users/me/organizations');
        return responseData;
    }
    async createOrganization(data) {
        const { data: responseData } = await this.api.post('/v1/organizations', data);
        return responseData;
    }
    async updateOrganization(organizationId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}`, data);
        return responseData;
    }
    async deleteOrganization(organizationId) {
        await this.api.delete(`/v1/organizations/${organizationId}`);
    }
    async leaveOrganization(organizationId) {
        await this.api.delete(`/v1/organizations/${organizationId}/leave`);
    }
    async getOrganization(id) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${id}`);
        return responseData;
    }
    async getOrganizationMembers(organizationId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/members`);
        return responseData;
    }
    async addMemberToOrganization(organizationId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/members`, data);
        return responseData;
    }
    async updateOrganizationMember(organizationId, memberId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/members/${memberId}`, data);
        return responseData;
    }
    async deleteMemberFormOrganization(organizationId, memberId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/members/${memberId}`);
        return responseData;
    }
    async getOrganizationOrbits(organizationId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits`);
        return responseData;
    }
    async createOrbit(organization_id, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organization_id}/orbits`, data);
        return responseData;
    }
    async getOrbitDetails(organizationId, orbitId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}`);
        return responseData;
    }
    async updateOrbit(organizationId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${data.id}`, data);
        return responseData;
    }
    async deleteOrbit(organizationId, orbitId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}`);
        return responseData;
    }
    async getOrbitMembers(organizationId, orbitId) {
        const { data: responseData } = await this.api.get(`/v1/organizations/${organizationId}/orbits/${orbitId}/members`);
        return responseData;
    }
    async addMemberToOrbit(organizationId, data) {
        const { data: responseData } = await this.api.post(`/v1/organizations/${organizationId}/orbits/${data.orbit_id}/members`, data);
        return responseData;
    }
    async updateOrbitMember(organizationId, orbitId, data) {
        const { data: responseData } = await this.api.patch(`/v1/organizations/${organizationId}/orbits/${orbitId}/members/${data.id}`, data);
        return responseData;
    }
    async deleteOrbitMember(organizationId, orbitId, memberId) {
        const { data: responseData } = await this.api.delete(`/v1/organizations/${organizationId}/orbits/${orbitId}/members/${memberId}`);
        return responseData;
    }
}
