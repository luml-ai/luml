import axios from 'axios';
const STORAGE_KEY = 'luml-agent-backend-url';
const DEFAULT_BACKEND_URL = 'http://localhost:8420';
export function getStoredBackendUrl() {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BACKEND_URL;
}
export function setStoredBackendUrl(url) {
    localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''));
}
export class PrismaApi {
    api;
    backendUrl;
    constructor() {
        this.backendUrl = getStoredBackendUrl();
        this.api = axios.create();
        this.api.interceptors.request.use((config) => {
            config.baseURL = `${this.backendUrl}/api`;
            return config;
        });
    }
    wsBaseUrl() {
        const parsed = new URL(this.backendUrl);
        const proto = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${proto}//${parsed.host}/ws`;
    }
    setBackendUrl(url) {
        this.backendUrl = url.replace(/\/+$/, '');
        setStoredBackendUrl(this.backendUrl);
    }
    getBackendUrl() {
        return this.backendUrl;
    }
    async health() {
        const { data } = await this.api.get('/health/');
        return data;
    }
    async listRepositories() {
        const { data } = await this.api.get('/repositories');
        return data;
    }
    async createRepository(body) {
        const { data } = await this.api.post('/repositories', body);
        return data;
    }
    async deleteRepository(id) {
        await this.api.delete(`/repositories/${id}`);
    }
    async listTasks(repositoryId) {
        const params = repositoryId != null ? { repository_id: repositoryId } : {};
        const { data } = await this.api.get('/tasks', { params });
        return data;
    }
    async createTask(body) {
        const { data } = await this.api.post('/tasks', body);
        return data;
    }
    async getTask(id) {
        const { data } = await this.api.get(`/tasks/${id}`);
        return data;
    }
    async deleteTask(id) {
        await this.api.delete(`/tasks/${id}`);
    }
    async reorderTasks(items) {
        await this.api.patch('/tasks/reorder', { items });
    }
    async updateTaskStatus(id, status) {
        const { data } = await this.api.patch(`/tasks/${id}/status`, { status });
        return data;
    }
    async getMergePreview(taskId) {
        const { data } = await this.api.post(`/tasks/${taskId}/merge/preview`);
        return data;
    }
    async mergeTask(taskId) {
        const { data } = await this.api.post(`/tasks/${taskId}/merge`);
        return data;
    }
    async browsePath(path, config) {
        const params = path != null ? { path } : {};
        const { data } = await this.api.get('/browse', { params, signal: config?.signal });
        return data;
    }
    async listBranches(path, config) {
        const { data } = await this.api.get('/browse/branches', {
            params: { path },
            signal: config?.signal,
        });
        return data.branches;
    }
    async listAvailableAgents() {
        const { data } = await this.api.get('/agents/available');
        return data;
    }
    async openTerminal(taskId, mode = 'agent') {
        const { data } = await this.api.post(`/tasks/${taskId}/terminal`, null, {
            params: { mode },
        });
        return data;
    }
    async listRuns(repositoryId) {
        const params = repositoryId != null ? { repository_id: repositoryId } : {};
        const { data } = await this.api.get('/runs', { params });
        return data;
    }
    async createRun(body) {
        const { data } = await this.api.post('/runs', body);
        return data;
    }
    async getRun(id) {
        const { data } = await this.api.get(`/runs/${id}`);
        return data;
    }
    async startRun(id) {
        const { data } = await this.api.post(`/runs/${id}/start`);
        return data;
    }
    async cancelRun(id) {
        const { data } = await this.api.post(`/runs/${id}/cancel`);
        return data;
    }
    async restartRun(id) {
        const { data } = await this.api.post(`/runs/${id}/restart`);
        return data;
    }
    async deleteRun(id) {
        await this.api.delete(`/runs/${id}`);
    }
    async reorderRuns(items) {
        await this.api.patch('/runs/reorder', { items });
    }
    async getRunGraph(id) {
        const { data } = await this.api.get(`/runs/${id}/graph`);
        return data;
    }
    async getRunEvents(id, afterSeq = 0) {
        const { data } = await this.api.get(`/runs/${id}/events`, {
            params: { after_seq: afterSeq },
        });
        return data;
    }
    async getRunMergePreview(runId) {
        const { data } = await this.api.post(`/runs/${runId}/merge/preview`);
        return data;
    }
    async mergeRun(runId) {
        const { data } = await this.api.post(`/runs/${runId}/merge`);
        return data;
    }
    async sendNodeAction(nodeId, action, payload = {}) {
        await this.api.post(`/nodes/${nodeId}/action`, { action, payload });
    }
    async getSessionScrollback(nodeId, sessionId) {
        const { data } = await this.api.get(`/nodes/${nodeId}/sessions/${sessionId}/scrollback`, {
            responseType: 'arraybuffer',
        });
        return data;
    }
    async getDebugSessions() {
        const { data } = await this.api.get('/debug/sessions');
        return data;
    }
    createTerminalWebSocket(sessionId) {
        return new WebSocket(`${this.wsBaseUrl()}/terminal/${sessionId}`);
    }
    async getPendingUploads(runId) {
        const { data } = await this.api.get(`/runs/${runId}/uploads`, {
            params: { status: 'pending' },
        });
        return data;
    }
    async postUploadUrl(runId, uploadId, presignedUrl) {
        const resp = await this.api.post(`/runs/${runId}/uploads/${uploadId}/url`, { presigned_url: presignedUrl }, { validateStatus: (s) => s === 202 || s === 409 });
        return resp.status;
    }
    async postArtifactLink(runId, uploadId, artifactLink) {
        await this.api.post(`/runs/${runId}/uploads/${uploadId}/artifact-link`, artifactLink);
    }
    createRunWebSocket(runId) {
        return new WebSocket(`${this.wsBaseUrl()}/runs/${runId}`);
    }
}
