import type { AgentRepository, AgentTask, Agent, MergePreview, RepositoryCreate, TaskCreate, BrowseResult, Run, RunCreate, RunGraph, RunEvent, PendingUpload } from './prisma.interfaces';
export declare function getStoredBackendUrl(): string;
export declare function setStoredBackendUrl(url: string): void;
export interface HealthResponse {
    service: string;
    version: string;
}
export declare class PrismaApi {
    private api;
    private backendUrl;
    constructor();
    private wsBaseUrl;
    setBackendUrl(url: string): void;
    getBackendUrl(): string;
    health(): Promise<HealthResponse>;
    listRepositories(): Promise<AgentRepository[]>;
    createRepository(body: RepositoryCreate): Promise<AgentRepository>;
    deleteRepository(id: string): Promise<void>;
    listTasks(repositoryId?: string): Promise<AgentTask[]>;
    createTask(body: TaskCreate): Promise<AgentTask>;
    getTask(id: string): Promise<AgentTask>;
    deleteTask(id: string): Promise<void>;
    reorderTasks(items: {
        id: string;
        position: number;
    }[]): Promise<void>;
    updateTaskStatus(id: string, status: string): Promise<AgentTask>;
    getMergePreview(taskId: string): Promise<MergePreview>;
    mergeTask(taskId: string): Promise<{
        status: string;
        message: string;
    }>;
    browsePath(path?: string, config?: {
        signal?: AbortSignal;
    }): Promise<BrowseResult>;
    listBranches(path: string, config?: {
        signal?: AbortSignal;
    }): Promise<string[]>;
    listAvailableAgents(): Promise<Agent[]>;
    openTerminal(taskId: string, mode?: 'agent' | 'shell'): Promise<AgentTask>;
    listRuns(repositoryId?: string): Promise<Run[]>;
    createRun(body: RunCreate): Promise<Run>;
    getRun(id: string): Promise<Run>;
    startRun(id: string): Promise<Run>;
    cancelRun(id: string): Promise<Run>;
    restartRun(id: string): Promise<Run>;
    deleteRun(id: string): Promise<void>;
    reorderRuns(items: {
        id: string;
        position: number;
    }[]): Promise<void>;
    getRunGraph(id: string): Promise<RunGraph>;
    getRunEvents(id: string, afterSeq?: number): Promise<RunEvent[]>;
    getRunMergePreview(runId: string): Promise<MergePreview>;
    mergeRun(runId: string): Promise<{
        status: string;
        message: string;
    }>;
    sendNodeAction(nodeId: string, action: string, payload?: Record<string, any>): Promise<void>;
    getSessionScrollback(nodeId: string, sessionId: string): Promise<ArrayBuffer>;
    getDebugSessions(): Promise<any[]>;
    createTerminalWebSocket(sessionId: string): WebSocket;
    getPendingUploads(runId: string): Promise<PendingUpload[]>;
    postUploadUrl(runId: string, uploadId: string, presignedUrl: string): Promise<number>;
    postArtifactLink(runId: string, uploadId: string, artifactLink: {
        artifact_id: string;
        organization_id: string;
        orbit_id: string;
        collection_id: string;
    }): Promise<void>;
    createRunWebSocket(runId: string): WebSocket;
}
