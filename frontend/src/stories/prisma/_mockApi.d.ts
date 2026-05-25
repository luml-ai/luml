import { api } from '@/lib/api';
import { mockAgents, mockBrowseResult, mockMergePreview, mockRepositories, mockTasks, mockRuns } from './_fixtures';
export interface PrismaApiOverrides {
    listAvailableAgents?: () => Promise<typeof mockAgents>;
    listBranches?: (path: string) => Promise<string[]>;
    browsePath?: (path?: string) => Promise<typeof mockBrowseResult>;
    getMergePreview?: (id: string) => Promise<typeof mockMergePreview>;
    getRunMergePreview?: (id: string) => Promise<typeof mockMergePreview>;
    mergeTask?: (id: string) => Promise<{
        status: string;
        message: string;
    }>;
    mergeRun?: (id: string) => Promise<{
        status: string;
        message: string;
    }>;
    createRepository?: typeof api.dataAgent.createRepository;
    createTask?: typeof api.dataAgent.createTask;
    createRun?: typeof api.dataAgent.createRun;
    listRepositories?: () => Promise<typeof mockRepositories>;
    listTasks?: () => Promise<typeof mockTasks>;
    listRuns?: () => Promise<typeof mockRuns>;
    getBackendUrl?: () => string;
    setBackendUrl?: (url: string) => void;
}
/**
 * Installs stubs on the shared `api.dataAgent` singleton. Safe to call from
 * decorators — later calls overwrite earlier ones.
 */
export declare function installPrismaApiStubs(overrides?: PrismaApiOverrides): void;
