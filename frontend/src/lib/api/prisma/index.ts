import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type {
  AgentRepository,
  AgentTask,
  Agent,
  MergePreview,
  RepositoryCreate,
  TaskCreate,
  BrowseResult,
  Run,
  RunCreate,
  RunGraph,
  RunEvent,
  PendingUpload,
} from './prisma.interfaces'

const STORAGE_KEY = 'luml-agent-backend-url'
const DEFAULT_BACKEND_URL = 'http://localhost:8420'

export function getStoredBackendUrl(): string {
  return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BACKEND_URL
}

export function setStoredBackendUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''))
}

export interface HealthResponse {
  service: string
  version: string
}

export class PrismaApi {
  private api: AxiosInstance
  private backendUrl: string

  constructor() {
    this.backendUrl = getStoredBackendUrl()
    this.api = axios.create()
    this.api.interceptors.request.use((config) => {
      config.baseURL = `${this.backendUrl}/api`
      return config
    })
  }

  private wsBaseUrl(): string {
    const parsed = new URL(this.backendUrl)
    const proto = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${parsed.host}/ws`
  }

  setBackendUrl(url: string): void {
    this.backendUrl = url.replace(/\/+$/, '')
    setStoredBackendUrl(this.backendUrl)
  }

  getBackendUrl(): string {
    return this.backendUrl
  }

  async health(): Promise<HealthResponse> {
    const { data } = await this.api.get<HealthResponse>('/health/')
    return data
  }

  async listRepositories(): Promise<AgentRepository[]> {
    const { data } = await this.api.get<AgentRepository[]>('/repositories')
    return data
  }

  async createRepository(body: RepositoryCreate): Promise<AgentRepository> {
    const { data } = await this.api.post<AgentRepository>('/repositories', body)
    return data
  }

  async deleteRepository(id: string): Promise<void> {
    await this.api.delete(`/repositories/${id}`)
  }

  async listTasks(repositoryId?: string): Promise<AgentTask[]> {
    const params = repositoryId != null ? { repository_id: repositoryId } : {}
    const { data } = await this.api.get<AgentTask[]>('/tasks', { params })
    return data
  }

  async createTask(body: TaskCreate): Promise<AgentTask> {
    const { data } = await this.api.post<AgentTask>('/tasks', body)
    return data
  }

  async getTask(id: string): Promise<AgentTask> {
    const { data } = await this.api.get<AgentTask>(`/tasks/${id}`)
    return data
  }

  async deleteTask(id: string): Promise<void> {
    await this.api.delete(`/tasks/${id}`)
  }

  async reorderTasks(items: { id: string; position: number }[]): Promise<void> {
    await this.api.patch('/tasks/reorder', { items })
  }

  async updateTaskStatus(id: string, status: string): Promise<AgentTask> {
    const { data } = await this.api.patch<AgentTask>(`/tasks/${id}/status`, { status })
    return data
  }

  async getMergePreview(taskId: string): Promise<MergePreview> {
    const { data } = await this.api.post<MergePreview>(`/tasks/${taskId}/merge/preview`)
    return data
  }

  async mergeTask(taskId: string): Promise<{ status: string; message: string }> {
    const { data } = await this.api.post(`/tasks/${taskId}/merge`)
    return data
  }

  async browsePath(path?: string, config?: { signal?: AbortSignal }): Promise<BrowseResult> {
    const params = path != null ? { path } : {}
    const { data } = await this.api.get<BrowseResult>('/browse', { params, signal: config?.signal })
    return data
  }

  async listBranches(path: string, config?: { signal?: AbortSignal }): Promise<string[]> {
    const { data } = await this.api.get<{ branches: string[] }>('/browse/branches', {
      params: { path },
      signal: config?.signal,
    })
    return data.branches
  }

  async listAvailableAgents(): Promise<Agent[]> {
    const { data } = await this.api.get<Agent[]>('/agents/available')
    return data
  }

  async openTerminal(taskId: string, mode: 'agent' | 'shell' = 'agent'): Promise<AgentTask> {
    const { data } = await this.api.post<AgentTask>(`/tasks/${taskId}/terminal`, null, {
      params: { mode },
    })
    return data
  }

  async listRuns(repositoryId?: string): Promise<Run[]> {
    const params = repositoryId != null ? { repository_id: repositoryId } : {}
    const { data } = await this.api.get<Run[]>('/runs', { params })
    return data
  }

  async createRun(body: RunCreate): Promise<Run> {
    const { data } = await this.api.post<Run>('/runs', body)
    return data
  }

  async getRun(id: string): Promise<Run> {
    const { data } = await this.api.get<Run>(`/runs/${id}`)
    return data
  }

  async startRun(id: string): Promise<Run> {
    const { data } = await this.api.post<Run>(`/runs/${id}/start`)
    return data
  }

  async cancelRun(id: string): Promise<Run> {
    const { data } = await this.api.post<Run>(`/runs/${id}/cancel`)
    return data
  }

  async restartRun(id: string): Promise<Run> {
    const { data } = await this.api.post<Run>(`/runs/${id}/restart`)
    return data
  }

  async deleteRun(id: string): Promise<void> {
    await this.api.delete(`/runs/${id}`)
  }

  async reorderRuns(items: { id: string; position: number }[]): Promise<void> {
    await this.api.patch('/runs/reorder', { items })
  }

  async getRunGraph(id: string): Promise<RunGraph> {
    const { data } = await this.api.get<RunGraph>(`/runs/${id}/graph`)
    return data
  }

  async getRunEvents(id: string, afterSeq: number = 0): Promise<RunEvent[]> {
    const { data } = await this.api.get<RunEvent[]>(`/runs/${id}/events`, {
      params: { after_seq: afterSeq },
    })
    return data
  }

  async getRunMergePreview(runId: string): Promise<MergePreview> {
    const { data } = await this.api.post<MergePreview>(`/runs/${runId}/merge/preview`)
    return data
  }

  async mergeRun(runId: string): Promise<{ status: string; message: string }> {
    const { data } = await this.api.post(`/runs/${runId}/merge`)
    return data
  }

  async sendNodeAction(nodeId: string, action: string, payload: Record<string, any> = {}): Promise<void> {
    await this.api.post(`/nodes/${nodeId}/action`, { action, payload })
  }

  async getSessionScrollback(nodeId: string, sessionId: string): Promise<ArrayBuffer> {
    const { data } = await this.api.get(`/nodes/${nodeId}/sessions/${sessionId}/scrollback`, {
      responseType: 'arraybuffer',
    })
    return data
  }

  async getDebugSessions(): Promise<any[]> {
    const { data } = await this.api.get('/debug/sessions')
    return data
  }

  createTerminalWebSocket(sessionId: string): WebSocket {
    return new WebSocket(`${this.wsBaseUrl()}/terminal/${sessionId}`)
  }

  async getPendingUploads(runId: string): Promise<PendingUpload[]> {
    const { data } = await this.api.get<PendingUpload[]>(`/runs/${runId}/uploads`, {
      params: { status: 'pending' },
    })
    return data
  }

  async postUploadUrl(runId: string, uploadId: string, presignedUrl: string): Promise<number> {
    const resp = await this.api.post(
      `/runs/${runId}/uploads/${uploadId}/url`,
      { presigned_url: presignedUrl },
      { validateStatus: (s) => s === 202 || s === 409 },
    )
    return resp.status
  }

  async postArtifactLink(
    runId: string,
    uploadId: string,
    artifactLink: { artifact_id: string; organization_id: string; orbit_id: string; collection_id: string },
  ): Promise<void> {
    await this.api.post(`/runs/${runId}/uploads/${uploadId}/artifact-link`, artifactLink)
  }

  createRunWebSocket(runId: string): WebSocket {
    return new WebSocket(`${this.wsBaseUrl()}/runs/${runId}`)
  }
}
